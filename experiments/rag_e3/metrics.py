"""
metrics.py — Metrics for E3 (asset retrieval + "no good asset" detection)
==========================================================================
Unlike E1, a scene can have several correct photos (two shots of the gate),
or none (no graduation photo uploaded).

Scenes WITH a correct photo:
  rank       position of the first correct photo (ties ranked pessimistically)
  Recall@k   share of scenes with a correct photo in the top k
  MRR        mean of 1/rank
  distractor share of scenes whose top-1 photo came from the distractors folder —
             e.g. another university's gate picked for "FAST main gate"

All scenes — fallback decision:
  The best photo's similarity score should be high when a fitting photo exists
  and low when none does. AUC measures how well that score separates the two
  (1.0 perfect, 0.5 coin flip). The threshold that best separates them is what
  the shot planner would use to fall back to stock / generation.
"""

from __future__ import annotations

import numpy as np

from visual_models import tie_aware_ranks

KS = (1, 3, 5)


def first_relevant_ranks(scores: np.ndarray, relevant: list[set[int]]) -> np.ndarray:
    """Rank of the best-ranked correct asset, for queries that have at least one."""
    ranks = tie_aware_ranks(scores)
    return np.array([min(ranks[q, a] for a in rel) for q, rel in enumerate(relevant) if rel])


def summarize(ranks: np.ndarray, ks=KS) -> dict[str, float]:
    ranks = np.asarray(ranks)
    out = {f"R@{k}": float(np.mean(ranks <= k)) for k in ks}
    out["MRR"] = float(np.mean(1.0 / ranks))
    return out


def bootstrap_ci(ranks: np.ndarray, k: int = 3, n_resamples: int = 2000, seed: int = 0) -> tuple[float, float]:
    """95% confidence interval of Recall@k by resampling scenes with replacement."""
    rng = np.random.default_rng(seed)
    samples = rng.choice(np.asarray(ranks), size=(n_resamples, len(ranks)), replace=True)
    low, high = np.percentile(np.mean(samples <= k, axis=1), [2.5, 97.5])
    return float(low), float(high)


def random_baseline(n_assets: int, relevant: list[set[int]], ks=KS, n_trials: int = 2000, seed: int = 0) -> dict:
    """Expected metrics if photos were ranked at random (simulated; scenes have different numbers of correct photos)."""
    rng = np.random.default_rng(seed)
    with_match = [rel for rel in relevant if rel]
    ranks = []
    for _ in range(n_trials):
        for rel in with_match:
            order = rng.permutation(n_assets)
            ranks.append(int(np.min(np.nonzero(np.isin(order, list(rel)))[0])) + 1)
    return summarize(np.array(ranks), ks)


def distractor_rate(scores: np.ndarray, relevant: list[set[int]], is_distractor: np.ndarray) -> float:
    """Share of scenes (with a match) whose top-1 photo is a distractor, not one of the creator's photos."""
    top1 = np.argmax(scores, axis=1)
    picks = [top1[q] for q, rel in enumerate(relevant) if rel]
    return float(np.mean([is_distractor[a] for a in picks])) if picks else 0.0


def auc(positive: np.ndarray, negative: np.ndarray) -> float:
    """Probability a random positive scores above a random negative (ties count half)."""
    if len(positive) == 0 or len(negative) == 0:
        return float("nan")
    pos = np.asarray(positive)[:, None]
    neg = np.asarray(negative)[None, :]
    return float(np.mean((pos > neg) + 0.5 * (pos == neg)))


def best_threshold(positive: np.ndarray, negative: np.ndarray) -> dict:
    """
    Threshold maximising balanced accuracy: (share of matching scenes kept +
    share of no-match scenes sent to fallback) / 2.

    Chosen on the same scenes it is scored on, so it is optimistic — with a
    few dozen scenes it is a starting value for the shot planner, not a final one.
    """
    if len(positive) == 0 or len(negative) == 0:
        return {}
    candidates = np.unique(np.concatenate([positive, negative]))
    best = None
    for t in candidates:
        kept = float(np.mean(positive >= t))
        rejected = float(np.mean(negative < t))
        balanced = (kept + rejected) / 2
        if best is None or balanced > best["balanced_accuracy"]:
            best = {"threshold": float(t), "matches_kept": kept, "no_match_rejected": rejected,
                    "balanced_accuracy": balanced}
    return best
