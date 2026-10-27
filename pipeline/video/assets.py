"""
assets.py — Asset Agent: one visual per shot
=============================================
Fallback chain for every shot query:

  0. Creator's own photo (personalised mode, if the creator supplied photos)
       SigLIP(photo, scene) >= threshold, best unused — creator_assets.py (E3)
  1. Pexels stock video (only if PEXELS_API_KEY is set)
       top-k portrait results → CLIP-score each thumbnail against the query
       → best unused clip with score ≥ CLIP_THRESHOLD is downloaded
  2. SDXL-Lightning still (local GPU)              → Ken Burns in renderer
  3. Placeholder card                              → pipeline never fails

CLIP is the same ViT-B/32 that Module 2 uses for the creator's own videos
(module2_multimodal_rag/visual_embedder.py), so "how well does this shot
match the idea" is measured with one instrument across the project.

Ranking (personalised vs generic is only the weight w):
  rank = text_score + w · creator_score
    text_score    CLIP(candidate, shot query)            — on-topic?
    creator_score CLIP(candidate) · creator centroid     — looks like the creator's videos?
  generic: w = 0 · personalised: w = CREATOR_WEIGHT (style_plan.py)
  The CLIP_THRESHOLD gate always uses text_score alone, so personalisation can
  never pull in an off-topic clip. Both modes see the same number of candidates
  (VIDEO_IMAGE_CANDIDATES SDXL seeds, PEXELS_CANDIDATES stock results), so the
  ablation isolates the ranking signal, not extra compute.

Everything downloaded or generated is cached under pipeline/cache/video_assets/
so re-renders and the personalised/generic comparison reuse the same assets.

Config (.env, optional):
  PEXELS_API_KEY  = ...     free key from https://www.pexels.com/api/
  CLIP_THRESHOLD  = 0.24    min CLIP cosine for a stock clip to be accepted
  VIDEO_IMAGE_CANDIDATES = 2   SDXL seeds generated per shot, best one kept
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import numpy as np
import requests

from .creator_assets import CreatorAssetLibrary, asset_id
from .creator_visual import CreatorVisual
from .image_gen import ImageGenError, SDXLLightning, image_gen_enabled, make_placeholder
from .timeline import Asset

PEXELS_SEARCH = "https://api.pexels.com/videos/search"
PEXELS_CANDIDATES = 8
DEFAULT_CLIP_THRESHOLD = 0.24
DEFAULT_IMAGE_CANDIDATES = 2
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
    """CLIP ViT-B/32 embeddings (Module 2's model) and image↔text cosine scores."""

    def __init__(self):
        self._tokenizer = None

    def text_embeddings(self, texts: list[str]) -> np.ndarray:
        import open_clip
        import torch

        from module2_multimodal_rag.visual_embedder import _load_clip

        model, _, device = _load_clip()
        if self._tokenizer is None:
            self._tokenizer = open_clip.get_tokenizer("ViT-B-32")
        with torch.no_grad():
            emb = model.encode_text(self._tokenizer(texts).to(device)).float()
            emb = emb / emb.norm(dim=-1, keepdim=True)
        return emb.cpu().numpy()

    def image_embeddings(self, image_paths: list[str]) -> np.ndarray:
        from module2_multimodal_rag.visual_embedder import embed_frames

        return embed_frames(image_paths).astype(np.float32)

    def score(self, image_paths: list[str], text: str) -> list[float]:
        sims = self.image_embeddings(image_paths) @ self.text_embeddings([text])[0]
        return [round(float(x), 4) for x in sims]


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
    resolve(query, image_prompt, used_ids, creator, creator_weight) → Asset,
    walking the fallback chain. `used_ids` stops the same stock clip
    appearing twice in one video.
    """

    def __init__(self, cache_dir: str | Path, pexels_key: str | None = None,
                 scorer: ClipScorer | None = None, image_gen: SDXLLightning | None = None,
                 clip_threshold: float | None = None, use_image_gen: bool | None = None,
                 image_candidates: int | None = None):
        self.cache_dir = Path(cache_dir)
        key = pexels_key if pexels_key is not None else os.getenv("PEXELS_API_KEY", "")
        self.pexels = PexelsSource(key, self.cache_dir) if key else None
        self.scorer = scorer
        self.image_gen = image_gen
        self.use_image_gen = image_gen_enabled() if use_image_gen is None else use_image_gen
        self.clip_threshold = clip_threshold if clip_threshold is not None else float(
            os.getenv("CLIP_THRESHOLD", DEFAULT_CLIP_THRESHOLD))
        self.image_candidates = max(1, image_candidates or int(
            os.getenv("VIDEO_IMAGE_CANDIDATES", DEFAULT_IMAGE_CANDIDATES)))
        self._scorer_failed = False
        self._image_gen_retried = False

    def _scorer(self) -> ClipScorer | None:
        if self._scorer_failed:
            return None
        if self.scorer is None:
            self.scorer = ClipScorer()
        return self.scorer

    def _rank(self, paths: list[str], query: str, creator: CreatorVisual | None,
              weight: float) -> list[tuple[float, float, float | None, int]] | None:
        """
        [(rank, text_score, creator_score, index)] best first, or None without CLIP.
        Scoring is optional: without CLIP we still render, we just can't rank.
        """
        scorer = self._scorer()
        if scorer is None or not paths:
            return None
        try:
            emb = scorer.image_embeddings(paths)
            text = emb @ scorer.text_embeddings([query])[0]
        except Exception as e:
            print(f"[Assets] CLIP scoring unavailable ({e}); assets will be unranked")
            self._scorer_failed = True
            return None
        styled = creator.similarity(emb) if creator is not None else [None] * len(paths)
        rows = []
        for i, (t, c) in enumerate(zip(text, styled)):
            t = round(float(t), 4)
            c = round(float(c), 4) if c is not None else None
            rows.append((t + weight * (c or 0.0), t, c, i))
        return sorted(rows, reverse=True)

    def _from_pexels(self, query: str, used_ids: set, creator, weight) -> Asset | None:
        try:
            videos = [v for v in self.pexels.search(query) if str(v["id"]) not in used_ids]
        except requests.RequestException as e:
            print(f"[Assets] Pexels search failed for {query!r}: {e}")
            return None
        thumbs, kept = [], []
        for v in videos:
            try:
                thumbs.append(str(self.pexels.thumbnail(v)))
                kept.append(v)
            except requests.RequestException:
                continue
        if not kept:
            return None

        ranked = self._rank(thumbs, query, creator, weight)
        if ranked is None:
            best, text_score, creator_score = kept[0], None, None
        else:
            # Threshold on the topic score only; the creator weight just orders on-topic clips
            on_topic = [r for r in ranked if r[1] >= self.clip_threshold]
            if not on_topic:
                return None   # nothing on-topic enough → let image gen try
            _, text_score, creator_score, idx = on_topic[0]
            best = kept[idx]

        try:
            path = self.pexels.download(best)
        except requests.RequestException as e:
            print(f"[Assets] Pexels download failed: {e}")
            return None
        used_ids.add(str(best["id"]))
        return Asset(path=str(path), kind="video", source="pexels", query=query,
                     clip_score=text_score, creator_score=creator_score, source_id=str(best["id"]),
                     note=f"pexels.com/video/{best['id']} by {best.get('user', {}).get('name', '?')}")

    def _from_image_gen(self, query: str, prompt: str, creator, weight) -> Asset | None:
        if self.image_gen is None:
            self.image_gen = SDXLLightning()
        base_seed = int(_key(prompt), 16) % (2 ** 31)
        paths = []
        try:
            for k in range(self.image_candidates):
                path = self.cache_dir / "sdxl" / f"{_key(prompt, str(k))}.png"
                if not path.exists():
                    self.image_gen.generate(prompt, path, seed=base_seed + k)
                paths.append(str(path))
        except Exception as e:   # model download, CUDA OOM, missing deps
            if not self._image_gen_retried and not isinstance(e, ImageGenError):
                # Usually CUDA OOM because another process (Ollama, a second job)
                # holds VRAM: free what we can and try once more before giving up
                self._image_gen_retried = True
                print(f"[Assets] Image generation failed ({e}); freeing GPU memory and retrying")
                self._free_gpu()
                return self._from_image_gen(query, prompt, creator, weight)
            print(f"[Assets] Image generation unavailable ({e}); using placeholder")
            self.use_image_gen = False
            if not paths:
                return None

        ranked = self._rank(paths, query, creator, weight)
        _, text_score, creator_score, idx = ranked[0] if ranked else (None, None, None, 0)
        return Asset(path=paths[idx], kind="image", source="sdxl", query=query,
                     clip_score=text_score, creator_score=creator_score,
                     note=f"{prompt} (best of {len(paths)})")

    def _from_creator_assets(self, query: str, scene: str, library: CreatorAssetLibrary,
                             used_ids: set) -> Asset | None:
        try:
            found = library.match(scene or query, used_ids)
        except Exception as e:   # model download / unreadable photo → normal chain
            print(f"[Assets] Creator photo matching unavailable ({e})")
            return None
        if found is None:
            return None
        path, score = found
        used_ids.add(asset_id(path))
        return Asset(path=str(path), kind="image", source="creator", query=query,
                     asset_score=score, source_id=path.name,
                     note=f"creator photo, SigLIP {score:.3f} >= {library.threshold}")

    @staticmethod
    def creator_photo(library: CreatorAssetLibrary, name: str, scene: str, query: str) -> Asset:
        """The photo the creator confirmed for this scene in the review step (any score)."""
        path = library.path_of(name)
        if path is None:
            raise ValueError(f"No creator photo named {name!r}")
        score = library.score_of(scene, name)
        return Asset(path=str(path), kind="image", source="creator", query=query,
                     asset_score=score, source_id=name, note="creator photo, confirmed by creator")

    def resolve(self, query: str, prompt: str = "", used_ids: set | None = None,
                creator: CreatorVisual | None = None, creator_weight: float = 0.0,
                creator_assets: CreatorAssetLibrary | None = None, scene: str = "") -> Asset:
        used_ids = used_ids if used_ids is not None else set()
        if creator_assets is not None:
            asset = self._from_creator_assets(query, scene, creator_assets, used_ids)
            if asset:
                return asset
        if self.pexels:
            asset = self._from_pexels(query, used_ids, creator, creator_weight)
            if asset:
                return asset
        if self.use_image_gen:
            asset = self._from_image_gen(query, prompt or query, creator, creator_weight)
            if asset:
                return asset
        path = make_placeholder(query, self.cache_dir / "placeholder" / f"{_key(query)}.png")
        return Asset(path=str(path), kind="image", source="placeholder", query=query,
                     note="no stock match and no image model available")

    def _free_gpu(self):
        """Unload Ollama and the half-loaded SDXL pipeline, then empty the CUDA cache."""
        from pipeline.local_llm import release_gpu

        release_gpu()
        if isinstance(self.image_gen, SDXLLightning):
            self.image_gen.unload()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

    def release(self):
        """Free GPU memory held by the image model."""
        if isinstance(self.image_gen, SDXLLightning):
            self.image_gen.unload()


__all__ = ["AssetResolver", "ClipScorer", "PexelsSource", "pick_video_file", "ImageGenError"]
