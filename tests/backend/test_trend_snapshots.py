"""
Tests for measured growth (daily view snapshots) and the channel-baseline
outlier. No network: the YouTube calls are faked.
"""
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

import pipeline.agents.research_agent as ra
from pipeline.agents import trend_snapshots as snap

DAY1 = datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc)
DAY2 = DAY1 + timedelta(days=1)


def _iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _v(vid, views, published, channel="c1"):
    return {"video_id": vid, "views": views, "published_at": _iso(published), "channel_id": channel}


# ── trend_snapshots ────────────────────────────────────────────────────────────

def test_niche_key_is_a_safe_folder_name():
    assert snap.niche_key("Beginner fitness & home workouts") == "beginner-fitness-home-workouts"
    assert snap.niche_key("!!!") == "default"


def test_save_and_load_roundtrip_merges_same_day(tmp_path):
    snap.save_snapshot(tmp_path, "n", DAY1, [_v("a", 100, DAY1 - timedelta(days=2))])
    snap.save_snapshot(tmp_path, "n", DAY1, [_v("b", 50, DAY1 - timedelta(days=1))])
    [today] = snap.load_history(tmp_path, "n", DAY1)
    assert set(today) == {"a", "b"}
    assert snap.tracked_ids([today]) == {"a", "b"}


def test_history_skips_files_older_than_window(tmp_path):
    old = DAY1 - timedelta(days=snap.HISTORY_DAYS + 2)
    snap.save_snapshot(tmp_path, "n", old, [_v("a", 1, old)])
    snap.save_snapshot(tmp_path, "n", DAY1, [_v("b", 1, DAY1)])
    assert [set(s) for s in snap.load_history(tmp_path, "n", DAY1)] == [{"b"}]


def test_acceleration_needs_a_snapshot_at_least_min_gap_old(tmp_path):
    pub = DAY1 - timedelta(days=4)
    snap.save_snapshot(tmp_path, "n", DAY1, [_v("a", 4000, pub)])
    history = snap.load_history(tmp_path, "n", DAY2)
    # same-day re-run: too close, nothing to compare with
    assert snap.acceleration("a", 5000, _iso(pub), DAY1 + timedelta(hours=3), history) is None
    assert snap.acceleration("new", 10, _iso(pub), DAY2, history) is None


def test_acceleration_separates_decaying_from_speeding_up(tmp_path):
    pub = DAY1 - timedelta(days=4)                 # 4 days old at DAY1: 1000 views/day so far
    snap.save_snapshot(tmp_path, "n", DAY1, [_v("decay", 4000, pub), _v("hot", 4000, pub)])
    history = snap.load_history(tmp_path, "n", DAY2)
    decay = snap.acceleration("decay", 4200, _iso(pub), DAY2, history)   # +200 in a day
    hot = snap.acceleration("hot", 7000, _iso(pub), DAY2, history)       # +3000 in a day
    assert decay == pytest.approx((200 + 10) / (1000 + 10))
    assert hot == pytest.approx((3000 + 10) / (1000 + 10))
    assert decay < 1 < hot


def test_acceleration_never_negative_when_views_drop(tmp_path):
    pub = DAY1 - timedelta(days=2)
    snap.save_snapshot(tmp_path, "n", DAY1, [_v("a", 5000, pub)])
    history = snap.load_history(tmp_path, "n", DAY2)
    assert snap.acceleration("a", 4900, _iso(pub), DAY2, history) > 0


# ── measured growth inside build_trends ────────────────────────────────────────

def _cluster(accels, hours=(10, 20, 40, 200)):
    videos = []
    for i, (a, h) in enumerate(zip(accels, hours)):
        videos.append({
            "video_id": f"v{i}", "title": f"Topic title {i}", "description": "", "tags": [],
            "channel": f"ch{i % 3}", "channel_id": f"ch{i % 3}", "language": "en",
            "published_at": _iso(DAY2 - timedelta(hours=h)), "duration_s": 45,
            "views": 50_000, "likes": 2500, "comments": 10, "subscribers": 10_000,
            "channel_median_views": 10_000, "acceleration": a,
        })
    ra.score_videos(videos, DAY2)
    emb = np.stack([np.array([1.0, 0.01 * i, 0.0]) / np.linalg.norm([1.0, 0.01 * i, 0.0])
                    for i in range(len(videos))])
    return videos, emb


def test_measured_growth_replaces_the_estimate(monkeypatch):
    monkeypatch.setattr(ra, "REQUIRE_MEASURED_GROWTH", True)
    videos, emb = _cluster([2.0, 1.8, 1.6, 2.2])
    [t] = ra.build_trends(videos, emb, [[0, 1, 2, 3]], None, niche_acceleration=1.0)
    assert t["growth_source"] == "snapshot"
    assert t["measured_growth"] == pytest.approx(1.9)
    assert t["checks"]["growing"] and t["trend_type"] == "trend"
    assert "Measured since the last snapshot" in ra._why_trending(t)


def test_measured_slow_cluster_is_not_growing_even_if_estimate_says_so(monkeypatch):
    monkeypatch.setattr(ra, "REQUIRE_MEASURED_GROWTH", True)
    videos, emb = _cluster([0.5, 0.6, 0.4, 0.5])          # decaying like a normal Short
    [t] = ra.build_trends(videos, emb, [[0, 1, 2, 3]], None,
                          niche_share=3 / 14, niche_acceleration=0.5)
    assert t["relative_growth"] > ra.GROWTH_RATIO_MIN     # the old estimate would say growing
    assert not t["checks"]["growing"]
    assert t["trend_type"] == "evergreen"


def test_estimate_only_cluster_is_at_most_emerging(monkeypatch):
    monkeypatch.setattr(ra, "REQUIRE_MEASURED_GROWTH", True)
    videos, emb = _cluster([None, None, None, None])
    [t] = ra.build_trends(videos, emb, [[0, 1, 2, 3]], None, niche_share=3 / 14)
    assert t["growth_source"] == "estimate" and all(t["checks"].values())
    assert t["trend_type"] == "emerging" and t["low_confidence"]
    monkeypatch.setattr(ra, "REQUIRE_MEASURED_GROWTH", False)
    [t] = ra.build_trends(videos, emb, [[0, 1, 2, 3]], None, niche_share=3 / 14)
    assert t["trend_type"] == "trend"


def test_one_measured_post_is_not_enough(monkeypatch):
    monkeypatch.setattr(ra, "REQUIRE_MEASURED_GROWTH", True)
    videos, emb = _cluster([5.0, None, None, None])
    [t] = ra.build_trends(videos, emb, [[0, 1, 2, 3]], None, niche_acceleration=1.0)
    assert t["growth_source"] == "estimate" and t["measured_posts"] == 1


# ── channel-baseline outlier ───────────────────────────────────────────────────

def _yt(views, subs, median):
    return {"video_id": "x", "title": "t", "views": views, "likes": 0, "comments": 0,
            "subscribers": subs, "channel_median_views": median,
            "published_at": _iso(DAY2 - timedelta(hours=24)), "platform": "youtube"}


def test_outlier_uses_channel_median_views():
    v = _yt(60_000, 1_000_000, 20_000)
    ra.score_videos([v], DAY2)
    assert v["outlier"] == pytest.approx(3.0) and v["baseline_source"] == "channel_median"


def test_tiny_channel_cannot_fake_overperformance():
    # 0-sub channel whose Shorts usually get 300 views; this one got 3,000
    v = _yt(3_000, 0, 300)
    ra.score_videos([v], DAY2)
    assert v["outlier"] == pytest.approx(3_000 / ra.VIEW_BASELINE_FLOOR)
    assert v["outlier"] < ra.OVERPERFORM_OUTLIER


def test_outlier_falls_back_to_subscribers_without_baseline():
    v = _yt(50_000, 10_000, None)
    ra.score_videos([v], DAY2)
    assert v["outlier"] == pytest.approx(5.0) and v["baseline_source"] == "subscribers"


class _Resp:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


def test_channel_baseline_uses_older_shorts_only(monkeypatch, tmp_path):
    monkeypatch.setattr(ra, "CACHE_DIR", tmp_path)
    old = _iso(DAY2 - timedelta(days=10))
    new = _iso(DAY2 - timedelta(hours=5))
    uploads = [(f"o{i}", old) for i in range(6)] + [("long", old), ("fresh", new), ("self", old)]

    def fake_get(url, params, timeout):
        if url == ra.YOUTUBE_PLAYLIST_ITEMS_URL:
            return _Resp({"items": [{"contentDetails": {"videoId": v, "videoPublishedAt": p}}
                                    for v, p in uploads]})
        ids = params["id"].split(",")
        assert "fresh" not in ids and "self" not in ids     # too young / in this run
        return _Resp({"items": [{"id": v, "statistics": {"viewCount": str(1000 * (int(v[1:]) + 1)
                                                                          if v != "long" else 10**7)},
                                 "contentDetails": {"duration": "PT10M" if v == "long" else "PT40S"}}
                                for v in ids]})

    monkeypatch.setattr(ra.requests, "get", fake_get)
    out = ra._fetch_channel_baselines({"c1": "UUc1"}, "key", DAY2, exclude_ids={"self"})
    assert out["c1"] == pytest.approx(3500)                   # median of 1000..6000, long video ignored
    # second call comes from the week-long cache: no network
    monkeypatch.setattr(ra.requests, "get", lambda *a, **k: pytest.fail("should be cached"))
    assert ra._fetch_channel_baselines({"c1": "UUc1"}, "key", DAY2, set())["c1"] == pytest.approx(3500)


def test_channel_with_few_shorts_gets_no_baseline(monkeypatch, tmp_path):
    monkeypatch.setattr(ra, "CACHE_DIR", tmp_path)
    old = _iso(DAY2 - timedelta(days=10))

    def fake_get(url, params, timeout):
        if url == ra.YOUTUBE_PLAYLIST_ITEMS_URL:
            return _Resp({"items": [{"contentDetails": {"videoId": f"o{i}", "videoPublishedAt": old}}
                                    for i in range(3)]})
        return _Resp({"items": [{"id": v, "statistics": {"viewCount": "100"},
                                 "contentDetails": {"duration": "PT30S"}} for v in params["id"].split(",")]})

    monkeypatch.setattr(ra.requests, "get", fake_get)
    assert ra._fetch_channel_baselines({"c1": "UUc1"}, "key", DAY2, set())["c1"] is None


# ── _apply_snapshots: two days in a row ────────────────────────────────────────

def test_apply_snapshots_measures_on_day_two_and_refreshes_tracked(monkeypatch, tmp_path):
    monkeypatch.setattr(ra, "SNAPSHOT_DIR", tmp_path)
    pub = DAY1 - timedelta(days=2)
    day1 = [dict(_v("a", 2000, pub)), dict(_v("gone", 2000, pub))]
    monkeypatch.setattr(ra, "_fetch_view_counts", lambda ids, key: {})
    stats1: dict = {}
    ra._apply_snapshots(day1, "Fitness", DAY1, "key", stats1)
    assert day1[0]["acceleration"] is None and stats1["posts_measured"] == 0

    refreshed = []
    monkeypatch.setattr(ra, "_fetch_view_counts",
                        lambda ids, key: refreshed.extend(ids) or {i: 2100 for i in ids})
    day2 = [dict(_v("a", 4000, pub))]
    stats2: dict = {}
    ra._apply_snapshots(day2, "Fitness", DAY2, "key", stats2)
    assert day2[0]["acceleration"] == pytest.approx((2000 + 10) / (1000 + 10))
    assert refreshed == ["gone"] and stats2["tracked_refreshed"] == 1
    [today, _] = snap.load_history(tmp_path, "fitness", DAY2)
    assert today["gone"]["views"] == 2100 and today["a"]["views"] == 4000
