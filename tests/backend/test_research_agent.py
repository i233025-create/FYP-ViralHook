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
    monkeypatch.delenv("TREND_SOURCE", raising=False)   # default (youtube) in every test


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


def test_single_video_and_single_creator_clusters_are_hidden():
    videos, emb = _scored_world()
    # singletons are too small; the phone cluster is one channel's series
    assert ra.build_trends(videos[:2], emb[:2], [[0], [1]], None) == []
    assert ra.build_trends(videos, emb, [[3, 4, 5]], None) == []


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


# ── Trend definition: 4 checks + trend_type ────────────────────────────────────

def _cluster(n_channels, views, subs, hours, prefix="t"):
    """One cluster: video i goes to channel i % n_channels."""
    videos = [_video(f"{prefix}{i}", f"Topic title number {i}", f"ch{i % n_channels}",
                     views[i], subs, hours_ago=h) for i, h in enumerate(hours)]
    ra.score_videos(videos, NOW)
    emb = np.stack([_unit(1, 0.01 * i, 0) for i in range(len(videos))])
    return videos, emb


def _types(videos, emb):
    return ra.build_trends(videos, emb, [list(range(len(videos)))], None)


def test_growth_ratio_counts_recent_vs_earlier_uploads():
    videos, _ = _cluster(3, [10_000] * 4, 1_000, hours=[10, 20, 30, 200])
    g = ra.growth_stats(videos)
    assert (g["recent_count"], g["earlier_count"]) == (3, 1)
    assert g["growth_ratio"] == pytest.approx((3 / 3 + 0.5) / (1 / 11 + 0.5), abs=1e-3)


def test_growth_edge_cases_no_division_by_zero():
    old, _ = _cluster(3, [10_000] * 3, 1_000, hours=[200, 250, 300])
    new, _ = _cluster(3, [10_000] * 3, 1_000, hours=[5, 6, 7])
    assert ra.growth_stats(old)["growth_ratio"] < 1
    assert ra.growth_stats(new)["growth_ratio"] > ra.GROWTH_RATIO_MIN
    assert ra.growth_stats([])["growth_ratio"] == 1.0


def test_trend_when_all_four_checks_pass():
    videos, emb = _cluster(3, [50_000] * 4, 10_000, hours=[10, 20, 40, 200])
    [t] = _types(videos, emb)
    assert t["trend_type"] == "trend"
    assert all(t["checks"].values())
    assert not t["low_confidence"]
    assert "as fast as the niche overall" in ra._why_trending(t)


def test_growing_is_relative_to_the_whole_niche():
    # every cluster gets the same recent-upload boost from sampling → cancels out
    videos, emb = _cluster(3, [50_000] * 4, 10_000, hours=[10, 20, 40, 200])
    share = ra.recent_share(videos)                         # 3 of 4 recent
    [same] = ra.build_trends(videos, emb, [[0, 1, 2, 3]], None, niche_share=share)
    assert same["relative_growth"] == pytest.approx(1.0)
    assert not same["checks"]["growing"]
    [faster] = ra.build_trends(videos, emb, [[0, 1, 2, 3]], None, niche_share=3 / 14)
    assert faster["checks"]["growing"] and faster["trend_type"] == "trend"


def test_relative_growth_shrinks_small_clusters_toward_the_niche():
    p = 0.6                                                  # recency-biased sample
    assert ra.relative_growth(3, 0, p) > ra.GROWTH_RATIO_MIN   # all recent → growing
    assert ra.relative_growth(1, 2, p) < 1                     # mostly old → not
    assert ra.relative_growth(0, 0, p) == pytest.approx(1.0)   # no data → like the niche
    assert ra.recent_share([]) == 0.5


def test_evergreen_when_spread_but_not_growing():
    videos, emb = _cluster(3, [50_000] * 4, 10_000, hours=[150, 200, 250, 300])
    [t] = _types(videos, emb)
    assert t["trend_type"] == "evergreen"
    assert t["checks"]["spreading"] and not t["checks"]["growing"]
    assert t["low_confidence"]


def test_emerging_when_growing_and_overperforming_on_two_channels():
    videos, emb = _cluster(2, [50_000] * 3, 10_000, hours=[5, 10, 20])
    [t] = _types(videos, emb)
    assert t["trend_type"] == "emerging"


def test_one_off_viral_is_hidden():
    videos, emb = _cluster(1, [900_000, 5_000], 10_000, hours=[5, 10])
    assert _types(videos, emb) == []


def test_topic_when_spread_and_growing_but_not_overperforming():
    videos, emb = _cluster(3, [1_000] * 3, 10_000, hours=[5, 10, 20])
    [t] = _types(videos, emb)
    assert t["trend_type"] == "topic"
    assert not t["checks"]["overperforms"]


def test_ranking_puts_trend_before_evergreen_even_with_lower_score():
    trend_v, _ = _cluster(3, [3_000] * 3, 1_000, hours=[5, 10, 20], prefix="a")
    ever_v, _ = _cluster(4, [900_000] * 4, 1_000, hours=[150, 200, 250, 300], prefix="b")
    for v in ever_v:
        v["channel_id"] = "e" + v["channel_id"]
    videos = trend_v + ever_v
    ra.score_videos(videos, NOW)
    emb = np.stack([_unit(1, 0.01 * i, 0) for i in range(3)] +
                   [_unit(0, 1, 0.01 * i) for i in range(4)])
    trends = ra.build_trends(videos, emb, [[0, 1, 2], [3, 4, 5, 6]], None)
    assert [t["trend_type"] for t in trends] == ["trend", "evergreen"]


def test_thresholds_can_be_overridden_from_env(monkeypatch):
    monkeypatch.setenv("TREND_GROWTH_RATIO_MIN", "2.5")
    assert ra._env_number("GROWTH_RATIO_MIN", 1.3) == 2.5
    monkeypatch.setenv("TREND_GROWTH_RATIO_MIN", "abc")
    assert ra._env_number("GROWTH_RATIO_MIN", 1.3) == 1.3


def test_youtube_searches_both_windows(monkeypatch):
    calls = []
    monkeypatch.setattr(ra, "_search_video_ids",
                        lambda q, k, now, days: calls.append((q, days)) or [])
    ra.collect_videos(["a", "b"], "key", NOW)
    assert calls == [("a", 14), ("a", 3), ("b", 14), ("b", 3)]


def test_unknown_source_is_an_error(sample_creator_profile):
    result = ra.run_research(sample_creator_profile, "x", source="tiktok", now=NOW)
    assert result["trends"] == [] and "TREND_SOURCE" in result["error"]


def test_instagram_without_config_reports_what_is_missing(sample_creator_profile):
    result = ra.run_research(sample_creator_profile, "x", source="instagram", now=NOW,
                             ig_config={"access_token": "", "user_id": "", "creators": []})
    assert "IG_ACCESS_TOKEN" in result["error"] and "IG_CREATORS" in result["error"]


def test_node_output_carries_trend_type(monkeypatch, sample_creator_profile):
    videos, emb = _scored_world()
    for v in videos[3:]:                       # phone videos are older background
        v["published_at"] = _iso(250)
    monkeypatch.setattr(ra, "collect_videos", lambda q, k, now: [dict(v) for v in videos])
    monkeypatch.setattr(ra, "embed_texts", lambda texts: (
        np.stack([_unit(1, 0, 0)] * len(texts)) if len(texts) != len(videos) else emb))
    out = ra.research_agent({"creator_niche": "x", "creator_profile": sample_creator_profile},
                            run=lambda p, n: ra.run_research(p, n, api_key="k", now=NOW,
                                                             source="youtube"))
    ro = out["research_output"]
    assert ro["trend_type"] == "trend"
    assert set(ro["trend_checks"]) == {"overperforms", "growing", "spreading", "recent"}
