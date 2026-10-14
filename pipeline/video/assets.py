"""
assets.py — Asset Agent: one visual per shot
=============================================
Fallback chain for every shot query:

  1. Pexels stock video (only if PEXELS_API_KEY is set)
       top-k portrait results → CLIP-score each thumbnail against the query
       → best unused clip with score ≥ CLIP_THRESHOLD is downloaded
  2. SDXL-Lightning still (local GPU)              → Ken Burns in renderer
  3. Placeholder card                              → pipeline never fails

CLIP is the same ViT-B/32 that Module 2 uses for the creator's own videos
(module2_multimodal_rag/visual_embedder.py), so "how well does this shot
match the idea" is measured with one instrument across the project.

Everything downloaded or generated is cached under pipeline/cache/video_assets/
so re-renders and the personalised/generic comparison reuse the same assets.

Config (.env, optional):
  PEXELS_API_KEY  = ...     free key from https://www.pexels.com/api/
  CLIP_THRESHOLD  = 0.24    min CLIP cosine for a stock clip to be accepted
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import requests

from .image_gen import ImageGenError, SDXLLightning, image_gen_enabled, make_placeholder
from .timeline import Asset

PEXELS_SEARCH = "https://api.pexels.com/videos/search"
PEXELS_CANDIDATES = 8
DEFAULT_CLIP_THRESHOLD = 0.24
MIN_VIDEO_WIDTH = 720
HTTP_TIMEOUT = 30


def _key(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:16]


def _download(url: str, path: Path) -> Path:
    if path.exists() and path.stat().st_size > 0:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    with requests.get(url, stream=True, timeout=HTTP_TIMEOUT) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
    tmp.replace(path)
    return path


# ─── CLIP scorer ──────────────────────────────────────────────────────────────

class ClipScorer:
    """Cosine similarity between images and a text query (CLIP ViT-B/32)."""

    def __init__(self):
        self._tokenizer = None

    def score(self, image_paths: list[str], text: str) -> list[float]:
        import open_clip
        import torch

        from module2_multimodal_rag.visual_embedder import _load_clip, embed_frames

        model, _, device = _load_clip()
        if self._tokenizer is None:
            self._tokenizer = open_clip.get_tokenizer("ViT-B-32")
        with torch.no_grad():
            text_emb = model.encode_text(self._tokenizer([text]).to(device)).float()
            text_emb = text_emb / text_emb.norm(dim=-1, keepdim=True)
        image_emb = torch.from_numpy(embed_frames(image_paths)).to(device).float()
        return [round(float(s), 4) for s in (image_emb @ text_emb.T).squeeze(-1).cpu()]


# ─── Pexels ───────────────────────────────────────────────────────────────────

def pick_video_file(video: dict) -> dict | None:
    """Smallest portrait MP4 that is still ≥ 720 px wide (fast download, sharp enough)."""
    files = [f for f in video.get("video_files", [])
             if f.get("file_type") == "video/mp4" and f.get("width") and f.get("height")
             and f["height"] > f["width"] and f["width"] >= MIN_VIDEO_WIDTH]
    return min(files, key=lambda f: f["width"]) if files else None


class PexelsSource:
    def __init__(self, api_key: str, cache_dir: Path):
        self.api_key = api_key
        self.cache_dir = cache_dir / "pexels"

    def search(self, query: str, per_page: int = PEXELS_CANDIDATES) -> list[dict]:
        r = requests.get(PEXELS_SEARCH, headers={"Authorization": self.api_key},
                         params={"query": query, "orientation": "portrait",
                                 "per_page": per_page, "size": "medium"},
                         timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        return [v for v in r.json().get("videos", []) if pick_video_file(v) and v.get("image")]

    def thumbnail(self, video: dict) -> Path:
        return _download(video["image"], self.cache_dir / "thumbs" / f"{video['id']}.jpg")

    def download(self, video: dict) -> Path:
        return _download(pick_video_file(video)["link"], self.cache_dir / f"{video['id']}.mp4")


# ─── Resolver ─────────────────────────────────────────────────────────────────

class AssetResolver:
    """
    resolve(query, image_prompt, used_ids) → Asset, walking the fallback chain.
    `used_ids` stops the same stock clip appearing twice in one video.
    """

    def __init__(self, cache_dir: str | Path, pexels_key: str | None = None,
                 scorer: ClipScorer | None = None, image_gen: SDXLLightning | None = None,
                 clip_threshold: float | None = None, use_image_gen: bool | None = None):
        self.cache_dir = Path(cache_dir)
        key = pexels_key if pexels_key is not None else os.getenv("PEXELS_API_KEY", "")
        self.pexels = PexelsSource(key, self.cache_dir) if key else None
        self.scorer = scorer
        self.image_gen = image_gen
        self.use_image_gen = image_gen_enabled() if use_image_gen is None else use_image_gen
        self.clip_threshold = clip_threshold if clip_threshold is not None else float(
            os.getenv("CLIP_THRESHOLD", DEFAULT_CLIP_THRESHOLD))
        self._scorer_failed = False

    # Scoring is optional: without CLIP we still render, we just can't rank.
    def _score(self, paths: list[str], text: str) -> list[float] | None:
        if self._scorer_failed or not paths:
            return None
        if self.scorer is None:
            self.scorer = ClipScorer()
        try:
            return self.scorer.score(paths, text)
        except Exception as e:
            print(f"[Assets] CLIP scoring unavailable ({e}); assets will be unranked")
            self._scorer_failed = True
            return None

    def _from_pexels(self, query: str, used_ids: set) -> Asset | None:
        try:
            videos = [v for v in self.pexels.search(query) if str(v["id"]) not in used_ids]
        except requests.RequestException as e:
            print(f"[Assets] Pexels search failed for {query!r}: {e}")
            return None
        if not videos:
            return None

        thumbs, kept = [], []
        for v in videos:
            try:
                thumbs.append(str(self.pexels.thumbnail(v)))
                kept.append(v)
            except requests.RequestException:
                continue
        scores = self._score(thumbs, query)
        if scores is None:
            best, best_score = (kept[0], None) if kept else (None, None)
        else:
            ranked = sorted(zip(scores, range(len(kept))), reverse=True)
            if not ranked or ranked[0][0] < self.clip_threshold:
                return None   # nothing on-topic enough → let image gen try
            best_score, idx = ranked[0]
            best = kept[idx]
        if best is None:
            return None

        try:
            path = self.pexels.download(best)
        except requests.RequestException as e:
            print(f"[Assets] Pexels download failed: {e}")
            return None
        used_ids.add(str(best["id"]))
        return Asset(path=str(path), kind="video", source="pexels", query=query,
                     clip_score=best_score, source_id=str(best["id"]),
                     note=f"pexels.com/video/{best['id']} by {best.get('user', {}).get('name', '?')}")

    def _from_image_gen(self, query: str, prompt: str) -> Asset | None:
        if self.image_gen is None:
            self.image_gen = SDXLLightning()
        path = self.cache_dir / "sdxl" / f"{_key(prompt)}.png"
        try:
            if not path.exists():
                self.image_gen.generate(prompt, path)
        except Exception as e:   # model download, CUDA OOM, missing deps
            print(f"[Assets] Image generation unavailable ({e}); using placeholder")
            self.use_image_gen = False
            return None
        scores = self._score([str(path)], query)
        return Asset(path=str(path), kind="image", source="sdxl", query=query,
                     clip_score=scores[0] if scores else None, note=prompt)

    def resolve(self, query: str, prompt: str = "", used_ids: set | None = None) -> Asset:
        used_ids = used_ids if used_ids is not None else set()
        if self.pexels:
            asset = self._from_pexels(query, used_ids)
            if asset:
                return asset
        if self.use_image_gen:
            asset = self._from_image_gen(query, prompt or query)
            if asset:
                return asset
        path = make_placeholder(query, self.cache_dir / "placeholder" / f"{_key(query)}.png")
        return Asset(path=str(path), kind="image", source="placeholder", query=query,
                     note="no stock match and no image model available")

    def release(self):
        """Free GPU memory held by the image model."""
        if isinstance(self.image_gen, SDXLLightning):
            self.image_gen.unload()


__all__ = ["AssetResolver", "ClipScorer", "PexelsSource", "pick_video_file", "ImageGenError"]
