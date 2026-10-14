"""
embeddings.py — Shared all-MiniLM-L6-v2 text embeddings
========================================================
One lazily-loaded SentenceTransformer (CPU) used by the Research Agent
(clustering, creator fit) and the Scripting Agent (example retrieval).
Same model as Module 1, so vectors are comparable across the project.
"""

from __future__ import annotations

import os

import numpy as np

EMBEDDING_MODEL = "all-MiniLM-L6-v2"

_embedder = None


def embed_texts(texts: list[str]) -> np.ndarray:
    """all-MiniLM-L6-v2 → (n, 384) L2-normalised matrix. Model loads once (CPU)."""
    global _embedder
    if _embedder is None:
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer(EMBEDDING_MODEL, device="cpu")
    return np.asarray(_embedder.encode(texts, normalize_embeddings=True, show_progress_bar=False))
