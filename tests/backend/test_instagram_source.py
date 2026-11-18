"""
test_instagram_source.py — Unit tests for the V2 (Instagram) research source.

No network and no token: requests.get is replaced by a fake Graph API that
returns payloads in the documented Business Discovery / Hashtag shapes.
Embeddings are faked so clustering is deterministic.
"""

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

import pipeline.agents.instagram_source as ig
import pipeline.agents.research_agent as ra
from pipeline.local_llm import LocalLLMError

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
CONFIG = {"access_token": "tok", "user_id": "1784", "creators": ["alice", "bob", "carol"],
          "hashtags": [], "graph_version": "v23.0"}


def _ts(hours_ago: float) -> str:
    return (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%S+0000")


def _media(mid, caption, likes, hours_ago, comments=10, product="REELS", hide_likes=False):
    item = {"id": mid, "caption": caption, "comments_count": comments,
            "timestamp": _ts(hours_ago), "media_type": "VIDEO",
            "media_product_type": product, "permalink": f"https://www.instagram.com/reel/{mid}/"}
    if not hide_likes:
        item["like_count"] = likes
    return item


def _history(prefix, n=8, likes=1_000):
    """Older posts (> 14 days) that only set the creator's baseline."""
    return [_media(f"{prefix}_old{i}", "An older post about something else", likes, 24 * 30 + i)
            for i in range(n)]


class FakeResponse:
    def __init__(self, body, status=200):
        self._body, self.status_code, self.text = body, status, str(body)
        self.ok = status < 400

    def json(self):
        return self._body


class FakeGraph:
    """Routes requests.get calls like the Graph API would."""

    def __init__(self, creators, hashtags=None, bad=()):
        self.creators, self.hashtags, self.bad, self.calls = creators, hashtags or {}, bad, []

    def __call__(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        if "business_discovery" in params.get("fields", ""):
            name = params["fields"].split("username(")[1].split(")")[0]
            if name in self.bad or name not in self.creators:
                return FakeResponse({"error": {"code": 110, "message": "Invalid user id"}}, 400)
            followers, media = self.creators[name]
            return FakeResponse({"business_discovery": {
                "username": name, "followers_count": followers, "media": {"data": media}}})
        if url.endswith("ig_hashtag_search"):
            tag = params["q"]
            return FakeResponse({"data": [{"id": f"h_{tag}"}] if tag in self.hashtags else []})
        tag_id, edge = url.rsplit("/", 2)[-2:]
        media = self.hashtags.get(tag_id[2:], {}).get(edge, [])
        return FakeResponse({"data": media})


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    """Fresh cache dir per test, LLM unavailable."""
    monkeypatch.setattr(ra, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(ig, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(ig, "USAGE_FILE", tmp_path / "usage.json")

    def fail(*a, **k):
        raise LocalLLMError("no LLM (test)")
    monkeypatch.setattr(ra, "chat_json", fail)


# ── Config ─────────────────────────────────────────────────────────────────────

def test_config_from_env(monkeypatch):
    monkeypatch.setenv("IG_ACCESS_TOKEN", "t")
    monkeypatch.setenv("IG_USER_ID", "1")
    monkeypatch.setenv("IG_CREATORS", " @Alice, bob ,,")
    monkeypatch.setenv("IG_HASHTAGS", "#Morning, gym")
    cfg = ig.config_from_env()
    assert cfg["creators"] == ["alice", "bob"]
    assert cfg["hashtags"] == ["morning", "gym"]
    assert ig.missing_config(cfg) == []
    assert ig.missing_config({"access_token": "t"}) == ["IG_USER_ID", "IG_CREATORS"]


# ── Post shaping ───────────────────────────────────────────────────────────────

def test_caption_title_takes_first_real_line():
    assert ig.caption_title("🔥🔥\n\nStop scrolling and start building today\n#motivation") == \
        "Stop scrolling and start building today"
    long = "word " * 60
    assert len(ig.caption_title(long)) <= ig.MAX_TITLE_CHARS


def test_timestamp_converted_to_utc_z():
    assert ig._to_utc_z("2026-11-10T17:00:00+0500") == "2026-11-10T12:00:00Z"
    assert ig._to_utc_z("garbage") == ""


def test_usable_filters():
    cutoff = NOW - timedelta(days=14)
    good = _media("m", "Morning routine that changed my life", 500, 10)
    assert ig._usable(good, cutoff)
    assert not ig._usable({**good, "media_product_type": "FEED"}, cutoff)       # not a Reel
    assert not ig._usable(_media("m", "Morning routine that changed my life", 0, 10,
                                 hide_likes=True), cutoff)                      # likes hidden
    assert not ig._usable(_media("m", "Morning routine that changed", 5, 24 * 20), cutoff)
    assert not ig._usable(_media("m", "#reels #fyp", 5, 10), cutoff)          # no real words


def test_creator_baseline_is_median_and_needs_enough_posts():
    media = [_media(str(i), "x y z", likes, 1, comments=0) for i, likes in
             enumerate([100, 200, 300, 400, 10_000])]
    assert ig.creator_baseline(media) == 300
    assert ig.creator_baseline(media[:3]) is None


def test_hashtags_from_queries():
    assert ig.hashtags_from_queries(["morning routine", "5am club!", "ok", "morning routine"]) == \
        ["morningroutine", "5amclub"]


def test_weekly_hashtag_limit(monkeypatch):
    monkeypatch.setattr(ig, "HASHTAG_WEEKLY_LIMIT", 2)
    assert ig.reserve_hashtags(["a1", "b1"], NOW) == (["a1", "b1"], [])
    # re-using a tag is free, a new one is over the limit
    assert ig.reserve_hashtags(["a1", "c1"], NOW) == (["a1"], ["c1"])
    # a week later the slots are free again
    assert ig.reserve_hashtags(["c1"], NOW + timedelta(days=8)) == (["c1"], [])


# ── collect_posts with a fake Graph API ────────────────────────────────────────

def _world():
    topic = "The 5AM morning routine that changed my life"
    return {
        "alice": (20_000, _history("a") + [_media("a1", topic, 4_000, 10),
                                            _media("a2", "Unrelated cooking video today", 900, 200)]),
        "bob": (50_000, _history("b") + [_media("b1", "My 5AM morning routine for focus", 3_500, 20),
                                          _media("b2", "Quick cooking recipe for dinner", 900, 230)]),
        "carol": (8_000, _history("c") + [_media("c1", "Why I wake up at 5AM every day", 5_000, 40),
                                           _media("c2", "Cooking pasta the easy way", 900, 260)]),
    }


def test_collect_posts_attributes_creators_and_baselines(monkeypatch):
    fake = FakeGraph(_world(), hashtags={"morningroutine": {
        "top_media": [_media("h1", "Morning routine ideas for busy people", 800, 15),
                      _media("a1", "dup of alice", 4_000, 10)],
        "recent_media": [_media("h2", "My simple morning routine checklist", 50, 2)]}})
    monkeypatch.setattr(ig.requests, "get", fake)
    posts, stats = ig.collect_posts(["morning routine"], CONFIG, NOW)

    by_id = {p["video_id"]: p for p in posts}
    assert set(by_id) == {"a1", "a2", "b1", "b2", "c1", "c2", "h1", "h2"}       # a1 not duplicated
    assert by_id["a1"]["channel_id"] == "alice" and by_id["a1"]["subscribers"] == 20_000
    assert by_id["a1"]["creator_baseline"] == 1_010                  # median likes+comments
    assert by_id["a1"]["found_via"] == "business_discovery"
    assert by_id["h1"]["channel_id"] == "" and by_id["h1"]["found_via"] == "hashtag:#morningroutine"
    assert stats["posts_from_creators"] == 6 and stats["posts_from_hashtags"] == 2
    assert stats["hashtags_used"] == ["morningroutine"]
    assert stats["api_calls"] == 3 + 3                              # 3 creators + search/top/recent


def test_personal_accounts_are_skipped_not_fatal(monkeypatch):
    monkeypatch.setattr(ig.requests, "get", FakeGraph(_world(), bad={"bob"}))
    posts, stats = ig.collect_posts(["x y"], CONFIG, NOW)
    assert "bob" in stats["failed_creators"]
    assert stats["creators_ok"] == 2
    assert all(p["channel_id"] != "bob" for p in posts)


def test_all_creators_failing_is_fatal(monkeypatch):
    monkeypatch.setattr(ig.requests, "get", FakeGraph({}, bad={"alice", "bob", "carol"}))
    with pytest.raises(ig.InstagramAPIError):
        ig.collect_posts(["x y"], CONFIG, NOW)


def test_expired_token_is_fatal(monkeypatch):
    monkeypatch.setattr(ig.requests, "get", lambda *a, **k: FakeResponse(
        {"error": {"code": 190, "message": "Error validating access token"}}, 400))
    with pytest.raises(ig.InstagramAPIError, match="190"):
        ig.collect_posts(["x y"], CONFIG, NOW)


def test_results_are_cached(monkeypatch):
    fake = FakeGraph(_world())
    monkeypatch.setattr(ig.requests, "get", fake)
    ig.collect_posts(["x y"], CONFIG, NOW)
    first = len(fake.calls)
    ig.collect_posts(["x y"], CONFIG, NOW)
    assert len(fake.calls) == first


# ── Scoring + full run (shared core) ───────────────────────────────────────────

def test_instagram_outlier_uses_creator_baseline_and_hashtag_has_none(monkeypatch):
    monkeypatch.setattr(ig.requests, "get", FakeGraph(_world(), hashtags={"tag": {
        "top_media": [_media("h1", "Morning routine ideas for busy people", 800, 15)]}}))
    posts, _ = ig.collect_posts(["tag"], CONFIG, NOW)
    ra.score_videos(posts, NOW)
    by_id = {p["video_id"]: p for p in posts}
    assert by_id["a1"]["outlier"] == pytest.approx(4_010 / 1_010)
    assert by_id["a1"]["engagement"] == pytest.approx(4_010 / 20_000)
    assert by_id["h1"]["outlier"] is None and by_id["h1"]["engagement"] is None
    assert all(0.0 <= p["video_score"] <= 1.0 for p in posts)


def test_run_research_instagram_end_to_end(monkeypatch, sample_creator_profile):
    monkeypatch.setattr(ig.requests, "get", FakeGraph(_world(), hashtags={"tag": {
        "top_media": [_media("h1", "Morning routine ideas for busy people", 800, 15)]}}))

    def fake_embed(texts):
        # the 5AM posts + the hashtag post share a direction; older cooking posts are
        # apart (they set the niche's background growth and fail the creator-fit gate)
        # (each gets its own small off-axis component so they aren't near-duplicates)
        rows = np.zeros((len(texts), 64))
        for i, t in enumerate(texts):
            rows[i, 1 if "cooking" in t.lower() else 0] = 1.0
            rows[i, 2 + i] = 0.4
        return rows / np.linalg.norm(rows, axis=1, keepdims=True)
    monkeypatch.setattr(ra, "embed_texts", fake_embed)

    result = ra.run_research(sample_creator_profile, "Personal growth", now=NOW,
                             source="instagram", ig_config={**CONFIG, "hashtags": ["tag"]})
    assert result["error"] is None, result["error"]
    assert result["source"] == "instagram_graph_api"
    [trend] = result["trends"]
    assert trend["trend_type"] == "trend"
    assert trend["channel_count"] == 3                  # hashtag post is not a creator
    assert trend["unattributed_count"] == 1
    assert trend["platform"] == "instagram"
    assert trend["evidence"][0]["url"].startswith("https://www.instagram.com/reel/")
    assert "Reels from 3 creators (+1 hashtag posts)" in trend["data_summary"]
    assert result["stats"]["api_cost"].endswith("Graph API calls (free)")


def test_hashtag_access_error_stops_hashtags_and_frees_slots(monkeypatch):
    graph = FakeGraph(_world())

    def get(url, params=None, timeout=None):
        if url.endswith("ig_hashtag_search"):
            graph.calls.append((url, params))
            return FakeResponse({"error": {"code": 10, "message":
                                 "To use 'Instagram Public Content Access', ... App Review"}}, 400)
        return graph(url, params, timeout)
    monkeypatch.setattr(ig.requests, "get", get)
    posts, stats = ig.collect_posts(["q"], {**CONFIG, "hashtags": ["one", "two", "three"]}, NOW)
    assert stats["hashtag_access"].startswith("unavailable")
    assert stats["hashtags_used"] == []
    assert sum(1 for u, _ in graph.calls if u.endswith("ig_hashtag_search")) == 1   # stopped early
    assert ig._load_usage(NOW) == {}                                                # slots freed
    assert stats["posts_from_creators"] > 0                                         # run went on
