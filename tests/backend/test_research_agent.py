"""
test_research_agent.py — Unit tests for the Research Agent.

No network, no YouTube key, no Ollama, no embedding model download:
the LLM is forced to fail (so fallbacks run) and embeddings are faked
with hand-made vectors so clustering is deterministic.
"""

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

import pipeline.agents.research_agent as ra
from pipeline.local_llm import LocalLLMError

NOW = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)


def _iso(hours_ago: float) -> str:
    return (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _video(vid, title, channel, views, subs, hours_ago=24, likes=None, comments=10):
    return {
        "video_id": vid, "title": title, "description": "", "tags": [],
        "channel": channel, "channel_id": channel, "language": "en",
        "published_at": _iso(hours_ago), "duration_s": 45,
        "views": views, "likes": likes if likes is not None else views // 20,
        "comments": comments, "subscribers": subs,
    }


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    """Every test runs with the local LLM unavailable."""
    def fail(*args, **kwargs):
        raise LocalLLMError("Ollama not running (test)")
    monkeypatch.setattr(ra, "chat_json", fail)


# ── [1] Queries ────────────────────────────────────────────────────────────────

def test_fallback_queries_come_from_profile(sample_creator_profile):
    queries = ra.generate_queries(sample_creator_profile, "Personal growth")
    assert queries[0] == "personal growth"
    assert "daily life frustrations" in queries
    assert len(queries) <= ra.MAX_QUERIES
    assert len(queries) == len(set(queries))


def test_llm_queries_are_validated_and_topped_up(monkeypatch, sample_creator_profile):
    monkeypatch.setattr(ra, "chat_json", lambda *a, **k: {
        "queries": ["5am morning routine", "x", 42, "5am morning routine",
                    "living fully: embracing mortality"]})
    queries = ra.generate_queries(sample_creator_profile, "Personal growth")
    assert queries[0] == "5am morning routine"
    assert "x" not in queries
    assert "living fully: embracing mortality" not in queries
    assert len(queries) == ra.MAX_QUERIES


def test_clean_topic_phrase_handles_unicode_hyphen():
    assert ra._clean_topic_phrase("Personal growth & self‑comparison") == \
        "personal growth self comparison"


# ── [2] Discovery helpers ──────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("PT45S", 45), ("PT1M5S", 65), ("PT3M", 180), ("PT1H", 3600), ("P0D", 0), ("", 0),
])
def test_parse_iso_duration(raw, expected):
    assert ra.parse_iso_duration(raw) == expected


def test_is_usable_filters_long_hidden_and_foreign():
    good = _video("a", "Stop comparing yourself today", "c", 5000, 10000)
    assert ra._is_usable(good)
    assert not ra._is_usable({**good, "duration_s": 600})
    assert not ra._is_usable({**good, "views": 50})
    assert not ra._is_usable({**good, "subscribers": None})
    assert not ra._is_usable({**good, "language": "hi"})
    assert ra._is_usable({**good, "language": "en-US"})
    assert ra._is_usable({**good, "language": ""})


@pytest.mark.parametrize("title", [
    "#motivation #jayakishorijibhajan #shortsfeed#quotes",   # hashtag-only
    "#motivational #sad #thankyou #shorts",
    "जीवन में सफलता का असली मंत्र #motivation",              # Devanagari, no lang tag
    "Trust 🔥🔥 #shorts",                                     # < 3 real words
])
def test_is_usable_drops_uninformative_titles(title):
    assert not ra._is_usable(_video("a", title, "c", 5000, 10000))


def test_is_usable_keeps_english_title_with_hashtags():
    assert ra._is_usable(_video("a", "Consistency Beats Intensity 🔥 | Keep Going! #Shorts", "c", 5000, 10000))


# ── [3] Scoring ────────────────────────────────────────────────────────────────

def test_outlier_favours_small_channel_over_big_channel():
    small = _video("s", "small", "small_ch", views=200_000, subs=5_000)
    big = _video("b", "big", "big_ch", views=300_000, subs=5_000_000)
    ra.score_videos([small, big], NOW)
    assert small["outlier"] == pytest.approx(40.0)
    assert small["video_score"] > big["video_score"]


def test_scores_are_bounded_and_floor_applies():
    tiny = _video("t", "tiny", "tiny_ch", views=2000, subs=10)
    other = _video("o", "other", "o_ch", views=9000, subs=50_000, hours_ago=5)
    ra.score_videos([tiny, other], NOW)
    assert tiny["outlier"] == pytest.approx(2000 / ra.SUBSCRIBER_FLOOR)
    for v in (tiny, other):
        assert 0.0 <= v["video_score"] <= 1.0


# ── [4] Clustering ─────────────────────────────────────────────────────────────

def _unit(*xs):
    v = np.array(xs, dtype=float)
    return v / np.linalg.norm(v)


def test_clustering_groups_by_meaning():
    emb = np.stack([
        _unit(1, 0.05, 0), _unit(1, 0, 0.05), _unit(0.95, 0.05, 0),   # topic A
        _unit(0, 1, 0.05), _unit(0.05, 1, 0),                         # topic B
        _unit(0, 0, 1),                                               # loner
    ])
    groups = sorted(sorted(g) for g in ra.cluster_embeddings(emb))
    assert groups == [[0, 1, 2], [3, 4], [5]]


def test_clustering_edge_cases():
    assert ra.cluster_embeddings(np.empty((0, 3))) == []
    assert ra.cluster_embeddings(np.stack([_unit(1, 0, 0)])) == [[0]]


def test_video_text_is_clean_title_only():
    v = _video("a", "I woke up at 5AM 😳 #shorts #viral", "c", 1, 1)
    v["description"] = "Follow for more #mindset #motivation"
    v["tags"] = ["mindset", "selfimprovement"]
    assert ra.video_text(v) == "I woke up at 5AM"


def test_is_usable_drops_non_latin_channel():
    video = _video("a", "Jeevitha satyalu inspiring quotes", "విఘ్నేశ్వరాయ", 5000, 10000)
    assert not ra._is_usable(video)
    assert ra._is_usable({**video, "channel": "🔥🔥"})   # no letters → not judged


# ── [5] Ranking + [6] Labeling ─────────────────────────────────────────────────

def _scored_world():
    videos = [
        _video("a1", "I woke up at 5AM for 30 days", "ch1", 90_000, 10_000),
        _video("a2", "What happens if you wake up early", "ch2", 60_000, 8_000),
        _video("a3", "5AM club changed my life #shorts", "ch3", 50_000, 20_000),
        _video("b1", "Best budget phone 2026", "ch4", 400_000, 900_000),
        _video("b2", "Budget phone review", "ch4", 300_000, 900_000),
        _video("b3", "Cheap phone camera test", "ch4", 200_000, 900_000),
    ]
    ra.score_videos(videos, NOW)
    emb = np.stack([_unit(1, 0.3, 0), _unit(1, 0, 0.3), _unit(1, -0.3, 0),
                    _unit(0.3, 1, 0), _unit(0, 1, 0.3), _unit(-0.3, 1, 0)])
    return videos, emb


def test_build_trends_requires_multiple_channels():
    videos, emb = _scored_world()
    clusters = ra.cluster_embeddings(emb)
    topics = np.stack([_unit(1, 0, 0)])      # creator talks about mornings
    trends = ra.build_trends(videos, emb, clusters, topics)

    # phone cluster is one channel only → dropped
    assert len(trends) == 1
    trend = trends[0]
    assert trend["video_count"] == 3 and trend["channel_count"] == 3
    assert trend["creator_fit"] > 0.95
    assert not trend["low_confidence"]
    assert trend["evidence"][0]["url"].startswith("https://www.youtube.com/shorts/")
    assert 0.0 <= trend["trend_score"] <= 1.0


def test_build_trends_low_confidence_when_nothing_qualifies():
    videos, emb = _scored_world()
    trends = ra.build_trends(videos[:2], emb[:2], [[0], [1]], None)
    assert trends and all(t["low_confidence"] for t in trends)
    assert all(t["creator_fit"] == 0.0 for t in trends)


def test_two_video_clusters_fill_slots_as_low_confidence():
    videos, emb = _scored_world()
    videos.append(_video("c1", "Stop overthinking tonight", "ch5", 20_000, 4_000))
    videos.append(_video("c2", "How to stop overthinking", "ch6", 15_000, 6_000))
    ra.score_videos(videos, NOW)
    emb = np.vstack([emb, _unit(0, 0.2, 1), _unit(0.2, 0, 1)])
    trends = ra.build_trends(videos, emb, ra.cluster_embeddings(emb), None)
    assert [t["video_count"] for t in trends] == [3, 2]
    assert [t["low_confidence"] for t in trends] == [False, True]


def test_near_duplicates_collapse_to_best_copy():
    videos = [
        _video("r1", "Most Powerful Quotes", "farm1", 10_000, 5_000),
        _video("r2", "Most Powerful Quotes", "farm2", 90_000, 5_000),
        _video("r3", "Most Powerful Quotes", "farm3", 20_000, 5_000),
        _video("u1", "Morning routine", "ch1", 30_000, 5_000),
    ]
    ra.score_videos(videos, NOW)
    emb = np.stack([_unit(1, 0, 0), _unit(1, 0.01, 0), _unit(1, 0, 0.01), _unit(0, 1, 0)])
    kept, kept_emb = ra.collapse_near_duplicates(videos, emb)
    assert [v["video_id"] for v in kept] == ["r2", "u1"]
    assert kept[0]["duplicate_count"] == 2
    assert np.allclose(kept_emb, emb[[1, 3]])


def test_label_fallback_uses_clean_title_and_real_numbers():
    videos, emb = _scored_world()
    trends = ra.build_trends(videos, emb, ra.cluster_embeddings(emb), None)
    ra.label_trends(trends, "Personal growth")
    trend = trends[0]
    assert trend["labeled_by"] == "title_fallback"
    assert "#" not in trend["topic"]
    assert "3 Shorts from 3 channels" in trend["data_summary"]
    assert "titles" not in trend


def test_label_uses_llm_text_when_available(monkeypatch):
    monkeypatch.setattr(ra, "chat_json", lambda *a, **k: {
        "topic": "Waking up at 5AM", "why_trending": "New-year energy.",
        "suggested_angle": "Contrarian take on early rising."})
    videos, emb = _scored_world()
    trends = ra.build_trends(videos, emb, ra.cluster_embeddings(emb), None)
    ra.label_trends(trends, "Personal growth")
    assert trends[0]["topic"] == "Waking up at 5AM"
    assert trends[0]["labeled_by"] == "local_llm"


def test_llm_text_is_trimmed_to_one_sentence(monkeypatch):
    monkeypatch.setattr(ra, "chat_json", lambda *a, **k: {
        "topic": "Comparison vs consistency",
        "why_trending": "People compare themselves daily. It also addresses a common struggle.",
        "suggested_angle": "Share a personal story! Then give tips."})
    videos, emb = _scored_world()
    trends = ra.build_trends(videos, emb, ra.cluster_embeddings(emb), None)
    ra.label_trends(trends, "Personal growth")
    assert trends[0]["why_trending"] == "People compare themselves daily."
    assert trends[0]["suggested_angle"] == "Share a personal story!"


def test_clusters_outside_the_niche_are_dropped():
    videos, emb = _scored_world()
    # creator's topic matches neither the mornings nor the phones cluster
    trends = ra.build_trends(videos, emb, ra.cluster_embeddings(emb), np.stack([_unit(0, 0, 1)]))
    assert trends == []


def test_run_research_reports_when_nothing_fits(monkeypatch, sample_creator_profile):
    videos, emb = _scored_world()
    monkeypatch.setattr(ra, "collect_videos", lambda q, k, now: [dict(v) for v in videos])
    monkeypatch.setattr(ra, "embed_texts", lambda texts: (
        np.stack([_unit(0, 0, 1)] * len(texts)) if len(texts) != len(videos) else emb))
    result = ra.run_research(sample_creator_profile, "Personal growth", api_key="k", now=NOW)
    assert result["trends"] == []
    assert "creator_fit" in result["error"]


def test_cluster_that_does_not_overperform_is_low_confidence():
    # 3 channels, but every video only got ~its subscriber count in views
    videos = [_video(f"p{i}", f"Trust the process {i}", f"ch{i}", 1_000 + i, 1_000) for i in range(3)]
    ra.score_videos(videos, NOW)
    emb = np.stack([_unit(1, 0.3, 0), _unit(1, 0, 0.3), _unit(1, -0.3, 0)])
    trends = ra.build_trends(videos, emb, ra.cluster_embeddings(emb), np.stack([_unit(1, 0, 0)]))
    assert len(trends) == 1
    assert trends[0]["median_outlier"] < ra.OVERPERFORM_OUTLIER
    assert trends[0]["low_confidence"]


def test_summary_uses_median_not_mean():
    videos, emb = _scored_world()
    videos[0]["views"] = 50_000_000            # one huge outlier video
    ra.score_videos(videos, NOW)
    trends = ra.build_trends(videos, emb, ra.cluster_embeddings(emb), None)
    assert trends[0]["median_outlier"] == pytest.approx(60_000 / 8_000)


# ── Orchestration / node ───────────────────────────────────────────────────────

def test_run_research_without_key_returns_error(sample_creator_profile):
    result = ra.run_research(sample_creator_profile, "Personal growth", api_key="", now=NOW)
    assert result["trends"] == []
    assert "YOUTUBE_API_KEY" in result["error"]


def test_run_research_end_to_end_with_fakes(monkeypatch, sample_creator_profile):
    videos, emb = _scored_world()
    monkeypatch.setattr(ra, "collect_videos", lambda q, k, now: [dict(v) for v in videos])
    monkeypatch.setattr(ra, "embed_texts", lambda texts: (
        np.stack([_unit(1, 0, 0)] * len(texts)) if len(texts) != len(videos) else emb))
    result = ra.run_research(sample_creator_profile, "Personal growth", api_key="k", now=NOW)
    assert result["error"] is None
    assert result["source"] == "youtube_data_api"
    assert len(result["trends"]) == 1


def test_node_falls_back_to_profile_topic_without_inventing_scores(sample_creator_profile):
    state = {"creator_id": "t", "creator_niche": "Personal growth",
             "creator_profile": sample_creator_profile}
    out = ra.research_agent(state, run=lambda p, n: {
        "trends": [], "queries": ["q"], "source": "none", "error": "YOUTUBE_API_KEY not set"})
    ro = out["research_output"]
    assert ro["topic"] == "Personal growth"
    assert ro["trend_score"] == 0.0
    assert ro["source"] == "profile_fallback"
    assert out["research_error"] == "YOUTUBE_API_KEY not set"


def test_node_never_crashes(sample_creator_profile):
    def boom(p, n):
        raise RuntimeError("model download failed")
    out = ra.research_agent({"creator_niche": "x", "creator_profile": sample_creator_profile},
                            run=boom)
    assert out["research_output"]["topic"]
    assert "model download failed" in out["research_error"]
