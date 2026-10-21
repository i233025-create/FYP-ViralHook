"""Unit tests for E3 — no models or photos needed. Run: python -m pytest tests"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from metrics import (auc, best_threshold, distractor_rate, first_relevant_ranks, random_baseline,
                     summarize)
from run_e3 import read_queries
from visual_models import Hybrid, make_retriever, tie_aware_ranks


def test_first_relevant_rank_takes_best_correct_photo():
    scores = np.array([[0.9, 0.5, 0.7, 0.1],    # correct: {1, 2} → photo 2 is 2nd
                       [0.2, 0.1, 0.3, 0.8],    # correct: {3}    → 1st
                       [0.5, 0.5, 0.5, 0.5]])   # no match → skipped
    ranks = first_relevant_ranks(scores, [{1, 2}, {3}, set()])
    assert ranks.tolist() == [2, 1]


def test_ties_are_pessimistic():
    assert tie_aware_ranks(np.array([[0.5, 0.5, 0.5]]))[0].tolist() == [3, 3, 3]


def test_summarize():
    m = summarize(np.array([1, 3, 6]), ks=(1, 3, 5))
    assert m["R@1"] == pytest.approx(1 / 3) and m["R@3"] == pytest.approx(2 / 3)
    assert m["MRR"] == pytest.approx((1 + 1 / 3 + 1 / 6) / 3)


def test_random_baseline_single_relevant():
    b = random_baseline(10, [{0}], n_trials=20000)
    assert b["R@1"] == pytest.approx(0.1, abs=0.01)
    assert b["R@3"] == pytest.approx(0.3, abs=0.015)


def test_distractor_rate():
    scores = np.array([[0.1, 0.9], [0.8, 0.2], [0.0, 1.0]])
    is_distractor = np.array([False, True])
    # scene 0 picks the distractor, scene 1 the creator photo, scene 2 has no match (ignored)
    assert distractor_rate(scores, [{0}, {0}, set()], is_distractor) == 0.5


def test_auc():
    assert auc(np.array([0.9, 0.8]), np.array([0.1, 0.2])) == 1.0
    assert auc(np.array([0.1]), np.array([0.9])) == 0.0
    assert auc(np.array([0.5]), np.array([0.5])) == 0.5


def test_best_threshold_separates_perfectly():
    t = best_threshold(np.array([0.30, 0.32, 0.35]), np.array([0.18, 0.20]))
    assert 0.20 < t["threshold"] <= 0.30
    assert t["matches_kept"] == 1.0 and t["no_match_rejected"] == 1.0


def test_read_queries(tmp_path):
    path = tmp_path / "queries.csv"
    path.write_text("query,relevant_files,category\n"
                    "Main gate,gate_1.jpg; gate_2.jpg,gate\n"
                    "Graduation,,\n"
                    ",,\n", encoding="utf-8")
    rows = read_queries(path)
    assert len(rows) == 2
    assert rows[0]["relevant_files"] == ["gate_1.jpg", "gate_2.jpg"]
    assert rows[1]["relevant_files"] == [] and rows[1]["category"] == "no_match"


def test_make_retriever():
    assert isinstance(make_retriever("siglip-base+caption"), Hybrid)
    assert make_retriever("siglip-base+caption").thresholdable is False
    with pytest.raises(ValueError):
        make_retriever("not-a-model")
