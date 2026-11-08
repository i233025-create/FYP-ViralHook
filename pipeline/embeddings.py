"""
embeddings.py — Shared text embeddings
=======================================
Two lazily-loaded SentenceTransformers (CPU):

  embed_texts            all-MiniLM-L6-v2 — Research Agent (clustering, creator
                         fit). Same model as Module 1, so vectors are comparable
                         across the project; its thresholds were tuned on it.
  embed_for_retrieval    intfloat/multilingual-e5-small — Scripting Agent
                         (topic → creator's past transcripts). Chosen by
                         experiment E1 (experiments/rag_e1/REPORT.md): R@3 89.0
                         vs 83.9 and R@1 58.1 vs 42.1 (significant) for MiniLM
                         on 41 real reels; on the Urdu–English food creator R@3
                         94.1 vs 58.8. e5 must see the "query: " / "passage: "
                         prefixes it was trained with.
"""

from __future__ import annotations

import os

import numpy as np

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
RETRIEVAL_MODEL = "intfloat/multilingual-e5-small"
RETRIEVAL_QUERY_PREFIX = "query: "
RETRIEVAL_PASSAGE_PREFIX = "passage: "

_models: dict = {}


def _model(name: str):
    if name not in _models:
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        from sentence_transformers import SentenceTransformer
        _models[name] = SentenceTransformer(name, device="cpu")
    return _models[name]


def embed_texts(texts: list[str]) -> np.ndarray:
    """all-MiniLM-L6-v2 → (n, 384) L2-normalised matrix. Model loads once (CPU)."""
    return np.asarray(_model(EMBEDDING_MODEL).encode(
        texts, normalize_embeddings=True, show_progress_bar=False))


def embed_for_retrieval(texts: list[str], is_query: bool) -> np.ndarray:
    """multilingual-e5-small → (n, 384) L2-normalised matrix, with e5's query/passage prefix."""
    prefix = RETRIEVAL_QUERY_PREFIX if is_query else RETRIEVAL_PASSAGE_PREFIX
    return np.asarray(_model(RETRIEVAL_MODEL).encode(
        [prefix + t for t in texts], normalize_embeddings=True, show_progress_bar=False))
