"""
creator_assets.py — Creator-supplied photos, matched to script scenes
======================================================================
Personalisation includes building the video around assets the creator
uploads (e.g. photos of their university for an "Admissions Open" reel).
For every shot, the best unused creator photo is used if it fits the scene;
otherwise the normal chain (Pexels → SDXL → placeholder) takes over.

Model and threshold come from experiment E3 (experiments/rag_e3/REPORT.md),
8 methods on 16 FAST photos + 10 other-university distractors, 41 scenes:

  SigLIP base (google/siglip-base-patch16-224)
    R@3 100% (13/13 scenes with a fitting photo) vs 84.6% for CLIP ViT-B/32,
    R@1 61.5% vs 53.8%, another university's photo ranked first 1/13 vs 2/13,
    no-match AUC 71.4 vs 59.3.
  Threshold 0.064 (cosine): keeps 62% of scenes that have a fitting photo and
    sends 82% of scenes without one to generation. It was fitted on the same
    scenes, so it is a default (CREATOR_ASSET_THRESHOLD), not a guarantee —
    the creator should review the chosen photo per scene.

CLIP ViT-B/32 stays in use for Pexels/SDXL ranking and the Module 2 creator
centroid (512-dim vectors already stored); E3 did not test those uses.

Photo embeddings are computed once per file and cached under
pipeline/cache/video_assets/creator_assets/.

CLI (shows the decision for each scene, for checking a library):
  python -m pipeline.video.creator_assets <photo folder> "A busy cafeteria" "A graduation ceremony"
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import numpy as np

SIGLIP_MODEL = "google/siglip-base-patch16-224"
DEFAULT_THRESHOLD = 0.064
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".jfif", ".bmp"}
BATCH = 8


def _normalize(x: np.ndarray) -> np.ndarray:
    return x / np.clip(np.linalg.norm(x, axis=-1, keepdims=True), 1e-9, None)


def _features(output) -> np.ndarray:
    """get_*_features → numpy (a tensor in transformers 4.x, a model output in 5.x)."""
    tensor = output if hasattr(output, "cpu") else output.pooler_output
    return tensor.detach().cpu().float().numpy()


def _file_key(path: Path) -> str:
    stat = path.stat()
    return hashlib.sha1(f"{SIGLIP_MODEL}|{path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}"
                        .encode()).hexdigest()[:16]


class SiglipEncoder:
    """SigLIP base on CPU (shares nothing with the GPU models), loaded on first use."""

    def __init__(self, model_id: str = SIGLIP_MODEL):
        self.model_id = model_id
        self._model = None

    def _load(self):
        if self._model is None:
            os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
            from transformers import AutoModel, AutoProcessor

            print(f"[CreatorAssets] Loading {self.model_id} (CPU)...")
            self._processor = AutoProcessor.from_pretrained(self.model_id)
            self._model = AutoModel.from_pretrained(self.model_id).eval()
        return self._model

    def image_embeddings(self, paths: list[Path]) -> np.ndarray:
        import torch
        from PIL import Image

        model = self._load()
        vecs = []
        for start in range(0, len(paths), BATCH):
            images = [Image.open(p).convert("RGB") for p in paths[start:start + BATCH]]
            batch = self._processor(images=images, return_tensors="pt")
            with torch.no_grad():
                vecs.append(_features(model.get_image_features(**batch)))
        return _normalize(np.concatenate(vecs))

    def text_embeddings(self, texts: list[str]) -> np.ndarray:
        import torch

        model = self._load()
        # SigLIP was trained on text padded to max_length; other padding hurts it (E3)
        batch = self._processor(text=texts, padding="max_length", truncation=True, return_tensors="pt")
        with torch.no_grad():
            return _normalize(_features(model.get_text_features(**batch)))


class CreatorAssetLibrary:
    """
    The creator's photos in one folder. match(scene, used_ids) → (path, score)
    of the best unused photo with score ≥ threshold, or None (→ fallback chain).
    """

    def __init__(self, folder: str | Path, cache_dir: str | Path | None = None,
                 threshold: float | None = None, encoder: SiglipEncoder | None = None):
        self.folder = Path(folder)
        self.paths = sorted(p for p in self.folder.iterdir()
                            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS) \
            if self.folder.is_dir() else []
        self.cache_dir = Path(cache_dir) / "creator_assets" if cache_dir else None
        self.threshold = threshold if threshold is not None else float(
            os.getenv("CREATOR_ASSET_THRESHOLD", DEFAULT_THRESHOLD))
        self.encoder = encoder or SiglipEncoder()
        self._vectors: np.ndarray | None = None

    def __len__(self) -> int:
        return len(self.paths)

    def _index(self) -> np.ndarray:
        """Photo embeddings, from the on-disk cache where possible."""
        if self._vectors is not None:
            return self._vectors
        cached: dict[int, np.ndarray] = {}
        if self.cache_dir:
            for i, p in enumerate(self.paths):
                f = self.cache_dir / f"{_file_key(p)}.npy"
                if f.exists():
                    cached[i] = np.load(f)
        todo = [i for i in range(len(self.paths)) if i not in cached]
        if todo:
            print(f"[CreatorAssets] Indexing {len(todo)} photo(s) in {self.folder}")
            fresh = self.encoder.image_embeddings([self.paths[i] for i in todo])
            for i, vec in zip(todo, fresh):
                cached[i] = vec
                if self.cache_dir:
                    self.cache_dir.mkdir(parents=True, exist_ok=True)
                    np.save(self.cache_dir / f"{_file_key(self.paths[i])}.npy", vec)
        self._vectors = np.stack([cached[i] for i in range(len(self.paths))])
        return self._vectors

    def rank(self, scene: str) -> list[tuple[float, Path]]:
        """All photos, best first, with their SigLIP cosine to the scene text."""
        if not self.paths:
            return []
        scores = self._index() @ self.encoder.text_embeddings([scene])[0]
        return sorted(((round(float(s), 4), p) for s, p in zip(scores, self.paths)),
                      key=lambda r: -r[0])

    def path_of(self, name: str) -> Path | None:
        return next((p for p in self.paths if p.name == name), None)

    def score_of(self, scene: str, name: str) -> float | None:
        return next((s for s, p in self.rank(scene) if p.name == name), None)

    def suggest(self, scenes: list[str]) -> list[dict]:
        """
        Review step: per scene, every photo ranked with its score, and the
        suggested one (best photo ≥ threshold not already suggested for an
        earlier scene, or None → stock / generated). The creator confirms or
        swaps these before rendering, because the threshold alone is not
        reliable (E3: no-match AUC 71).
        """
        used: set = set()
        out = []
        for scene in scenes:
            ranked = self.rank(scene)
            suggested = next((p.name for s, p in ranked
                              if s >= self.threshold and p.name not in used), None)
            if suggested:
                used.add(suggested)
            out.append({"ranked": [{"name": p.name, "score": s} for s, p in ranked],
                        "suggested": suggested})
        return out

    def match(self, scene: str, used_ids: set | None = None) -> tuple[Path, float] | None:
        used_ids = used_ids if used_ids is not None else set()
        for score, path in self.rank(scene):
            if score < self.threshold:
                return None
            if asset_id(path) not in used_ids:
                return path, score
        return None


def asset_id(path: Path) -> str:
    """Key in the resolver's used_ids set, so one photo is used once per video."""
    return f"creator:{Path(path).name}"


def load_creator_assets(folder: str | Path | None, cache_dir: str | Path | None = None
                        ) -> CreatorAssetLibrary | None:
    """Library for `folder` (or CREATOR_ASSETS_DIR); None if there are no photos."""
    folder = folder or os.getenv("CREATOR_ASSETS_DIR", "")
    if not folder:
        return None
    library = CreatorAssetLibrary(folder, cache_dir)
    if not library.paths:
        print(f"[CreatorAssets] No photos in {folder}; using stock/generated visuals only")
        return None
    return library


def main(argv: list[str] | None = None):
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) < 2:
        print(__doc__)
        return
    library = CreatorAssetLibrary(argv[0])
    print(f"{len(library)} photos, SigLIP threshold {library.threshold}\n")
    for scene in argv[1:]:
        ranked = library.rank(scene)
        best = ranked[0] if ranked else None
        decision = (f"USE {best[1].name}" if best and best[0] >= library.threshold
                    else "no photo fits -> stock / generated")
        print(f"{scene}\n  -> {decision}")
        for score, path in ranked[:3]:
            print(f"     {score:.3f}  {path.name}")


__all__ = ["CreatorAssetLibrary", "SiglipEncoder", "asset_id", "load_creator_assets",
           "DEFAULT_THRESHOLD", "SIGLIP_MODEL"]


if __name__ == "__main__":
    main()
