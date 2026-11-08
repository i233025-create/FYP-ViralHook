"""
retrievers.py — The search methods compared in E1
==================================================
Every method does the same job: given queries (cleaned captions) and
documents (transcripts), return a score matrix scores[q, d] — higher means
document d is a better match for query q.

  BM25          keyword overlap, no neural network (classic baseline)
  RawBERT       plain BERT / mBERT, mean-pooled — NOT trained for similarity
  Dense         sentence-embedding models (MiniLM, mpnet, bge, e5, LaBSE, ...)
  Hybrid        BM25 + a dense model, merged with Reciprocal Rank Fusion
                (same k=60 RRF as module2_multimodal_rag/qdrant_store.py)

All models run on CPU (or GPU if available) and are downloaded from
Hugging Face on first use.
"""

from __future__ import annotations

import re

import numpy as np

MAX_TOKENS = 512   # reel transcripts are short; this only matters for bge-m3
RRF_K = 60


def _device() -> str:
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


def _tokenize(text: str) -> list[str]:
    # \w is Unicode-aware, so Urdu and Hindi words are kept as tokens.
    return re.findall(r"\w+", text.lower())


class Retriever:
    name: str = "base"
    family: str = ""
    params_m: float | None = None   # model size in millions of parameters

    def index(self, docs: list[str]) -> None:
        raise NotImplementedError

    def score(self, queries: list[str]) -> np.ndarray:
        raise NotImplementedError


class BM25(Retriever):
    family = "keyword"

    def __init__(self, name: str = "bm25"):
        self.name = name

    def index(self, docs: list[str]) -> None:
        from rank_bm25 import BM25Okapi
        # BM25Okapi fails on an empty token list; a placeholder token keeps it valid.
        self._bm25 = BM25Okapi([_tokenize(d) or ["<empty>"] for d in docs])

    def score(self, queries: list[str]) -> np.ndarray:
        return np.array([self._bm25.get_scores(_tokenize(q)) for q in queries], dtype=np.float32)


class _EmbeddingRetriever(Retriever):
    """Shared logic: embed queries and docs, score with cosine similarity."""

    def _embed(self, texts: list[str], is_query: bool) -> np.ndarray:
        raise NotImplementedError

    def index(self, docs: list[str]) -> None:
        self._doc_vecs = self._embed(docs, is_query=False)

    def score(self, queries: list[str]) -> np.ndarray:
        return self._embed(queries, is_query=True) @ self._doc_vecs.T


class Dense(_EmbeddingRetriever):
    """A sentence-transformers model, with the query/passage prefixes it was trained with."""

    family = "sentence-embedding"

    def __init__(self, name: str, model_id: str, query_prefix: str = "", doc_prefix: str = ""):
        self.name = name
        self.model_id = model_id
        self.query_prefix = query_prefix
        self.doc_prefix = doc_prefix
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_id, device=_device())
            self._model.max_seq_length = min(self._model.max_seq_length or MAX_TOKENS, MAX_TOKENS)
            self.params_m = round(sum(p.numel() for p in self._model.parameters()) / 1e6, 1)
        return self._model

    def _embed(self, texts: list[str], is_query: bool) -> np.ndarray:
        prefix = self.query_prefix if is_query else self.doc_prefix
        return np.asarray(self._load().encode([prefix + t for t in texts], batch_size=16,
                                              normalize_embeddings=True, show_progress_bar=False))


class RawBERT(_EmbeddingRetriever):
    """
    Plain pre-trained BERT with mean pooling over tokens.

    BERT was trained to fill in masked words, not to put similar sentences
    close together, so this is expected to do poorly. It is the control that
    shows why sentence-embedding fine-tuning matters.
    """

    family = "raw-bert"

    def __init__(self, name: str, model_id: str):
        self.name = name
        self.model_id = model_id
        self._model = None

    def _load(self):
        if self._model is None:
            from transformers import AutoModel, AutoTokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_id)
            self._model = AutoModel.from_pretrained(self.model_id).to(_device()).eval()
            self.params_m = round(sum(p.numel() for p in self._model.parameters()) / 1e6, 1)
        return self._model

    def _embed(self, texts: list[str], is_query: bool) -> np.ndarray:
        import torch
        model = self._load()
        out = []
        for start in range(0, len(texts), 16):
            batch = self._tokenizer(texts[start:start + 16], padding=True, truncation=True,
                                    max_length=MAX_TOKENS, return_tensors="pt").to(model.device)
            with torch.no_grad():
                hidden = model(**batch).last_hidden_state
            mask = batch["attention_mask"].unsqueeze(-1).float()
            pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
            out.append(torch.nn.functional.normalize(pooled, dim=-1).cpu().numpy())
        return np.concatenate(out)


class Hybrid(Retriever):
    """Reciprocal Rank Fusion of two retrievers: score = Σ 1 / (k + rank)."""

    family = "hybrid"

    def __init__(self, name: str, first: Retriever, second: Retriever):
        self.name = name
        self.parts = (first, second)

    def index(self, docs: list[str]) -> None:
        for part in self.parts:
            part.index(docs)
        self.params_m = sum(p.params_m or 0 for p in self.parts) or None

    def score(self, queries: list[str]) -> np.ndarray:
        return sum(rrf_scores(part.score(queries)) for part in self.parts)


def tie_aware_ranks(scores: np.ndarray) -> np.ndarray:
    """
    rank[q, d] = number of docs scoring >= doc d for query q (rank 1 = best).

    Ties get the worst shared rank, so a method gains nothing from a tie —
    e.g. BM25 scoring every doc 0 ranks them all last, not the first doc first.
    """
    return (scores[:, None, :] >= scores[:, :, None]).sum(axis=-1)


def rrf_scores(scores: np.ndarray, k: int = RRF_K) -> np.ndarray:
    """Score matrix → RRF contribution 1/(k + rank) per (query, doc)."""
    return 1.0 / (k + tie_aware_ranks(scores))


# ─── Registry ──────────────────────────────────────────────────────────────────
# name → (factory, multilingual?)

BGE_QUERY = "Represent this sentence for searching relevant passages: "

METHODS: dict[str, tuple] = {
    # English methods
    "bm25":            (lambda: BM25(), True),
    "bert-raw":        (lambda: RawBERT("bert-raw", "bert-base-uncased"), False),
    "minilm":          (lambda: Dense("minilm", "sentence-transformers/all-MiniLM-L6-v2"), False),
    "mpnet":           (lambda: Dense("mpnet", "sentence-transformers/all-mpnet-base-v2"), False),
    "bge-small":       (lambda: Dense("bge-small", "BAAI/bge-small-en-v1.5", query_prefix=BGE_QUERY), False),
    "e5-small":        (lambda: Dense("e5-small", "intfloat/e5-small-v2", "query: ", "passage: "), False),
    # Multilingual methods
    "mbert-raw":       (lambda: RawBERT("mbert-raw", "bert-base-multilingual-cased"), True),
    "multi-minilm":    (lambda: Dense("multi-minilm",
                                      "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"), True),
    "multi-e5-small":  (lambda: Dense("multi-e5-small", "intfloat/multilingual-e5-small",
                                      "query: ", "passage: "), True),
    "labse":           (lambda: Dense("labse", "sentence-transformers/LaBSE"), True),
    "bge-m3":          (lambda: Dense("bge-m3", "BAAI/bge-m3"), True),
}

DEFAULT_METHODS = list(METHODS) + ["bm25+minilm", "bm25+multi-e5-small"]
QUICK_METHODS = ["bm25", "bert-raw", "minilm", "bge-small", "multi-e5-small", "bm25+minilm"]


def make_retriever(name: str) -> Retriever:
    """'minilm' → single method; 'bm25+minilm' → RRF hybrid of the two."""
    if "+" in name:
        first, second = name.split("+", 1)
        return Hybrid(name, make_retriever(first), make_retriever(second))
    if name not in METHODS:
        raise ValueError(f"Unknown method '{name}'. Known: {', '.join(METHODS)} (or 'a+b' for a hybrid)")
    return METHODS[name][0]()


def is_multilingual(name: str) -> bool:
    return all(METHODS[part][1] for part in name.split("+"))
