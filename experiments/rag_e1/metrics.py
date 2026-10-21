"""
metrics.py — Known-item retrieval metrics for E1
=================================================
Query i (reel i's caption) has exactly one correct document: reel i's own
transcript, which sits at index i. So the correct answers are the diagonal
of the score matrix.

  Recall@k   share of queries whose correct transcript is in the top k
  MRR        mean of 1/rank of the correct transcript (1.0 = always first)

Ties are ranked pessimistically (see retrievers.tie_aware_ranks).
"""

from __future__ import annotations

import numpy as np

from retrievers import tie_aware_ranks

KS = (1, 3, 5)


def correct_ranks(scores: np.ndarray) -> np.ndarray:
    """Rank of the correct (diagonal) document for each query."""
    idx = np.arange(scores.shape[0])
    return tie_aware_ranks(scores)[idx, idx]


def summarize(ranks: np.ndarray, ks=KS) -> dict[str, float]:
    ranks = np.asarray(ranks)
    out = {f"R@{k}": float(np.mean(ranks <= k)) for k in ks}
    out["MRR"] = float(np.mean(1.0 / ranks))
    return out


def random_baseline(n_docs: int, ks=KS) -> dict[str, float]:
    """Expected scores when documents are shuffled at random."""
    out = {f"R@{k}": min(k, n_docs) / n_docs for k in ks}
    out["MRR"] = float(np.sum(1.0 / np.arange(1, n_docs + 1)) / n_docs)
    return out


def bootstrap_ci(ranks: np.ndarray, metric: str, n_resamples: int = 2000, seed: int = 0) -> tuple[float, float]:
    """95% confidence interval of a metric by resampling queries with replacement."""
    ranks = np.asarray(ranks)
    rng = np.random.default_rng(seed)
    samples = rng.choice(ranks, size=(n_resamples, len(ranks)), replace=True)
    if metric == "MRR":
        values = np.mean(1.0 / samples, axis=1)
    else:
        k = int(metric.split("@")[1])
        values = np.mean(samples <= k, axis=1)
    low, high = np.percentile(values, [2.5, 97.5])
    return float(low), float(high)
