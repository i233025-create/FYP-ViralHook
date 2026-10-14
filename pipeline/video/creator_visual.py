"""
creator_visual.py — The creator's visual look, from Module 2's CLIP vectors
============================================================================
Module 2 stored one 512-dim CLIP ViT-B/32 vector per creator video (mean of
its frames) in qdrant_snapshot.json. The Video Agent uses them three ways:

  centroid        mean of the creator's video vectors = "what their videos look like"
                  → re-rank candidate shots (assets.py) and score the render (evaluator.py)
  describe_look() CLIP zero-shot over a small look vocabulary (lighting / colour /
                  setting) → words added to the SDXL prompt, e.g. "warm golden light"
  self_similarity leave-one-out: how close each creator video is to the others'
                  centroid — the reference ceiling for the evaluator's visual score

It is the same CLIP model as the asset scorer, so every comparison lives in
one embedding space.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "module2_multimodal_rag" / "qdrant_snapshot.json"

# One pick per group keeps the description coherent (never "warm" and "cool")
LOOK_VOCAB = {
    "lighting": ["warm golden light", "cool blue light", "dark moody low-key lighting",
                 "bright high-key lighting", "soft natural daylight"],
    "colour": ["vibrant saturated colours", "muted desaturated colours", "black and white",
               "soft pastel colours", "high contrast"],
    "setting": ["indoor home room", "outdoor nature", "city street", "plain studio backdrop",
                "office or desk workspace"],
}
LOOK_TEMPLATE = "a photo with {}"


def _normalize(v: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.where(norm == 0, 1, norm)


@dataclass
class CreatorVisual:
    vectors: np.ndarray                    # (n_videos, 512), L2-normalised
    talking_head_pct: float | None = None

    @property
    def centroid(self) -> np.ndarray:
        return _normalize(self.vectors.mean(axis=0))

    def similarity(self, embeddings: np.ndarray) -> np.ndarray:
        """Cosine of each (L2-normalised) embedding to the creator centroid."""
        return _normalize(np.atleast_2d(embeddings)) @ self.centroid

    def self_similarity(self) -> float | None:
        """Mean leave-one-out cosine of each creator video to the rest. None with < 2 videos."""
        n = len(self.vectors)
        if n < 2:
            return None
        sims = [float(self.vectors[i] @ _normalize(np.delete(self.vectors, i, axis=0).mean(axis=0)))
                for i in range(n)]
        return round(sum(sims) / n, 4)


def load_creator_visual(path: str | Path = SNAPSHOT) -> CreatorVisual | None:
    """None when Module 2 hasn't been run (no snapshot / no visual vectors)."""
    path = Path(path)
    if not path.exists():
        return None
    points = json.loads(path.read_text(encoding="utf-8")).get("points", [])
    vectors = [p["visual_vector"] for p in points if p.get("visual_vector") and any(p["visual_vector"])]
    if not vectors:
        return None
    th = [p["payload"]["talking_head_pct"] for p in points
          if isinstance(p.get("payload", {}).get("talking_head_pct"), (int, float))]
    return CreatorVisual(vectors=_normalize(np.asarray(vectors, dtype=np.float32)),
                         talking_head_pct=round(sum(th) / len(th), 4) if th else None)


def describe_look(creator: CreatorVisual, scorer) -> list[str]:
    """Best-matching look phrase per vocabulary group, e.g. ['warm golden light', ...]."""
    picks = []
    for terms in LOOK_VOCAB.values():
        text = scorer.text_embeddings([LOOK_TEMPLATE.format(t) for t in terms])
        picks.append(terms[int(np.argmax(text @ creator.centroid))])
    return picks
