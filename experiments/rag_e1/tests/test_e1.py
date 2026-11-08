"""Unit tests for E1 — no models or data needed. Run: python -m pytest tests"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from metrics import correct_ranks, random_baseline, summarize
from retrievers import BM25, Hybrid, is_multilingual, make_retriever, rrf_scores, tie_aware_ranks
from text_clean import clean_caption, detect_script, dominant_script, word_count


# ─── Caption cleaning ──────────────────────────────────────────────────────────

def test_clean_caption_removes_noise():
    raw = "This serum changed my skin 😍✨ Link in bio! #skincare #glowup @brand https://x.co/a"
    assert clean_caption(raw) == "This serum changed my skin"


def test_clean_caption_removes_cta_boilerplate():
    raw = "iPhone 16 battery test after 1 year 🔋 Follow for more tech tips! Save this reel"
    assert clean_caption(raw) == "iPhone 16 battery test after 1 year"


def test_clean_caption_removes_leftover_symbols_and_product_headers():
    raw = "Mutton pulao supremacy 🤌🏻Location- @hnfoodspk, F6 Markaz, Islamabad👕 @naqeesofficial & @vylax"
    assert clean_caption(raw) == "Mutton pulao supremacy Location- F6 Markaz, Islamabad"
    raw = "My GRWM for uni\n\nProducts mentioned:\n@brand concealer"
    assert clean_caption(raw) == "My GRWM for uni concealer"


def test_clean_caption_keeps_roman_and_urdu_script():
    assert clean_caption("yaar ye phone kamaal hai 🔥 #tech") == "yaar ye phone kamaal hai"
    assert clean_caption("یہ فون کمال ہے ✨") == "یہ فون کمال ہے"


def test_clean_caption_hashtag_only_is_empty():
    assert word_count(clean_caption("🔥🔥 #makeup #grwm")) == 0


def test_detect_script():
    assert dominant_script("hello world") == "latin"
    assert dominant_script("یہ فون کمال ہے") == "arabic"
    assert dominant_script("यह फोन कमाल है") == "devanagari"
    mixed = detect_script("ye phone یہ")
    assert mixed["latin"] > 0 and mixed["arabic"] > 0


# ─── Ranking and metrics ───────────────────────────────────────────────────────

def test_tie_aware_ranks_are_pessimistic():
    ranks = tie_aware_ranks(np.array([[0.0, 0.0, 0.0], [0.9, 0.5, 0.1]]))
    assert ranks[0].tolist() == [3, 3, 3]       # all tied → all last, no free wins
    assert ranks[1].tolist() == [1, 2, 3]


def test_correct_ranks_reads_diagonal():
    scores = np.array([[0.9, 0.1, 0.2],    # correct doc 0 first
                       [0.8, 0.3, 0.1],    # correct doc 1 second
                       [0.5, 0.6, 0.4]])   # correct doc 2 third
    assert correct_ranks(scores).tolist() == [1, 2, 3]


def test_summarize():
    m = summarize(np.array([1, 2, 4]), ks=(1, 3))
    assert m["R@1"] == pytest.approx(1 / 3)
    assert m["R@3"] == pytest.approx(2 / 3)
    assert m["MRR"] == pytest.approx((1 + 0.5 + 0.25) / 3)


def test_random_baseline():
    b = random_baseline(4, ks=(1, 3, 5))
    assert b["R@1"] == 0.25 and b["R@3"] == 0.75 and b["R@5"] == 1.0
    assert b["MRR"] == pytest.approx((1 + 1 / 2 + 1 / 3 + 1 / 4) / 4)


def test_rrf_prefers_doc_ranked_well_by_both():
    a = np.array([[0.9, 0.8, 0.1]])
    b = np.array([[0.7, 0.9, 0.1]])
    fused = rrf_scores(a) + rrf_scores(b)
    assert np.argmin(fused[0]) == 2


# ─── Retrievers (no model downloads) ───────────────────────────────────────────

def test_bm25_finds_keyword_match():
    bm25 = BM25()
    bm25.index(["iphone battery drains fast", "best lipstick for summer", "gaming laptop review"])
    scores = bm25.score(["lipstick summer", "laptop for gaming"])
    assert scores.argmax(axis=1).tolist() == [1, 2]


def test_bm25_handles_urdu_tokens_and_empty_docs():
    bm25 = BM25()
    bm25.index(["یہ فون کمال ہے", ""])
    assert bm25.score(["فون"])[0].argmax() == 0


def test_make_retriever_hybrid_and_unknown():
    assert isinstance(make_retriever("bm25+minilm"), Hybrid)
    with pytest.raises(ValueError):
        make_retriever("not-a-model")


def test_is_multilingual():
    assert is_multilingual("labse") and is_multilingual("bm25+multi-e5-small")
    assert not is_multilingual("minilm") and not is_multilingual("bm25+minilm")
