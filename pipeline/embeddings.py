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
# Urdu (script + Roman Urdu) niches: all-MiniLM-L6-v2 is English-only, so
# Urdu titles would get meaningless vectors. This model maps Urdu and English
# into one space (same 384 dims, same family). Used only when a niche asks for it.
MULTILINGUAL_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

_embedders: dict[str, object] = {}


def embed_texts(texts: list[str], model_name: str = EMBEDDING_MODEL) -> np.ndarray:
    """texts → (n, 384) L2-normalised matrix. Each model loads once (CPU)."""
    if model_name not in _embedders:
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        from sentence_transformers import SentenceTransformer
        _embedders[model_name] = SentenceTransformer(model_name, device="cpu")
    return np.asarray(_embedders[model_name].encode(texts, normalize_embeddings=True,
                                                    show_progress_bar=False))
