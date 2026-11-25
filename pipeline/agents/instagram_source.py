"""
instagram_source.py — V2 data source for the Research Agent (Instagram Graph API)
==================================================================================
Collects Instagram Reels in the same post shape the YouTube source uses, so
research_agent.py's scoring, clustering and trend definition run unchanged.

Two official endpoints (no scraping):

  Business Discovery   GET /{ig-user-id}?fields=business_discovery.username(X){...}
                       For each creator in a hand-picked niche list: followers
                       and their last 50 posts (caption, likes, comments, time).
                       → every check of the trend definition works, because the
                       author, follower count and the creator's own history are
                       known. outlier = post likes+comments ÷ the creator's median
                       likes+comments (their real "normal").
                       Limit: only Business/Creator accounts can be looked up.

  Hashtag Search       GET /ig_hashtag_search → GET /{hashtag-id}/top_media and
                       /recent_media (last 24 h only).
                       → discovery only: these posts have no username or follower
                       count, so they add volume to a cluster but never count as
                       a creator, never set over-performance and never feed growth.
                       Limit: 30 unique hashtags per 7 days per Instagram account,
                       tracked locally in pipeline/cache/ig_hashtag_usage.json.

What V2 measures is "what is working among THESE creators + these hashtags",
not all of Instagram. Views of other people's Reels are not in the API, so
likes + comments stand in for views everywhere.

Setup (.env): IG_ACCESS_TOKEN, IG_USER_ID (your IG professional account id),
IG_CREATORS (comma-separated usernames), optional IG_HASHTAGS, IG_GRAPH_VERSION.
"""

from __future__ import annotations

import json
import os
import re
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from pipeline.agents.research_agent import (
    CACHE_DIR, SEARCH_PUBLISHED_DAYS, _clean_text, _load_cache, _save_cache,
    _title_is_informative,
)

# ─── Configuration ─────────────────────────────────────────────────────────────
DEFAULT_GRAPH_VERSION = "v23.0"
GRAPH_URL = "https://graph.facebook.com/{version}"

BD_MEDIA_LIMIT = 50              # creator's last N posts: recent ones + baseline history
MIN_BASELINE_POSTS = 5           # fewer posts with likes → no reliable "normal"
HASHTAG_MEDIA_LIMIT = 50
MAX_HASHTAGS_PER_RUN = 5
HASHTAG_WEEKLY_LIMIT = 30        # Meta: 30 unique hashtags per 7 days per account
MAX_TITLE_CHARS = 150
REELS_ONLY = True                # short-form video creators: compare Reels with Reels

MEDIA_FIELDS = ("id,caption,like_count,comments_count,timestamp,media_type,"
                "media_product_type,permalink")
HASHTAG_MEDIA_FIELDS = "id,caption,like_count,comments_count,timestamp,media_type,permalink"
TOKEN_ERROR_CODES = {190, 102}   # expired/invalid token: stop the whole run

USAGE_FILE = CACHE_DIR / "ig_hashtag_usage.json"


class InstagramAPIError(Exception):
    """Fatal for the run (bad token, no permission). Per-item errors are skipped."""


# ─── Config ────────────────────────────────────────────────────────────────────

def _split_list(raw: str) -> list[str]:
    return [x.strip().lstrip("@#").lower() for x in raw.split(",") if x.strip()]


def config_from_env() -> dict:
    return {
        "access_token": os.getenv("IG_ACCESS_TOKEN", ""),
        "user_id": os.getenv("IG_USER_ID", ""),
        "creators": _split_list(os.getenv("IG_CREATORS", "")),
        "hashtags": _split_list(os.getenv("IG_HASHTAGS", "")),
        "graph_version": os.getenv("IG_GRAPH_VERSION", "") or DEFAULT_GRAPH_VERSION,
    }


def missing_config(config: dict) -> list[str]:
    names = {"access_token": "IG_ACCESS_TOKEN", "user_id": "IG_USER_ID",
             "creators": "IG_CREATORS"}
    return [env for key, env in names.items() if not config.get(key)]


# ─── HTTP ──────────────────────────────────────────────────────────────────────

class _ItemError(Exception):
    """One creator/hashtag failed (e.g. personal account); the run goes on."""


def _graph_get(path: str, params: dict, config: dict, stats: dict) -> dict:
    url = f"{GRAPH_URL.format(version=config.get('graph_version') or DEFAULT_GRAPH_VERSION)}/{path}"
    stats["api_calls"] = stats.get("api_calls", 0) + 1
    try:
        response = requests.get(url, params={**params, "access_token": config["access_token"]},
                                timeout=20)
    except requests.RequestException as e:
        raise InstagramAPIError(f"network error: {e}") from e
    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.ok and "error" not in body:
        return body
    err = body.get("error", {})
    message = f"HTTP {response.status_code} code={err.get('code')}: {err.get('message', response.text[:200])}"
    if err.get("code") in TOKEN_ERROR_CODES or response.status_code in (401,):
        raise InstagramAPIError(message)
    raise _ItemError(message)


# ─── Post shaping ──────────────────────────────────────────────────────────────

def _to_utc_z(timestamp: str) -> str:
    """'2026-11-10T12:34:56+0000' → '2026-11-10T12:34:56Z' (format the core expects)."""
    try:
        dt = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S%z")
    except (ValueError, TypeError):
        return ""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def caption_title(caption: str) -> str:
    """First non-empty caption line, trimmed at a word boundary: the Reel's 'title'."""
    for line in (caption or "").splitlines():
        if _clean_text(line):
            line = " ".join(line.split())
            if len(line) > MAX_TITLE_CHARS:
                line = line[:MAX_TITLE_CHARS].rsplit(" ", 1)[0]
            return line
    return ""


def _is_reel(item: dict) -> bool:
    if item.get("media_product_type"):
        return item["media_product_type"] == "REELS"
    return item.get("media_type") == "VIDEO"


def _post(item: dict, username: str, followers: int | None, baseline: float | None,
          found_via: str) -> dict:
    caption = item.get("caption") or ""
    return {
        "video_id": item["id"],
        "title": caption_title(caption),
        "description": caption[:300],
        "tags": re.findall(r"#(\w+)", caption)[:10],
        "channel": username,
        "channel_id": username,
        "language": "",
        "published_at": _to_utc_z(item.get("timestamp", "")),
        "duration_s": None,
        "views": None,                         # not exposed for other people's Reels
        "likes": int(item.get("like_count") or 0),
        "comments": int(item.get("comments_count") or 0),
        "subscribers": followers,
        "creator_baseline": baseline,
        "platform": "instagram",
        "url": item.get("permalink", ""),
        "found_via": found_via,
    }


def _usable(item: dict, cutoff: datetime) -> bool:
    """Reel, likes visible, inside the search window, informative English caption."""
    published = _to_utc_z(item.get("timestamp", ""))
    if not published:
        return False
    when = datetime.strptime(published, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return (
        when >= cutoff
        and "like_count" in item                       # missing = owner hides likes
        and (not REELS_ONLY or _is_reel(item))
        and _title_is_informative(caption_title(item.get("caption") or ""))
    )


# ─── Business Discovery ────────────────────────────────────────────────────────

def creator_baseline(media: list[dict]) -> float | None:
    """Median likes+comments over the creator's fetched posts = their normal."""
    counts = [int(m.get("like_count") or 0) + int(m.get("comments_count") or 0)
              for m in media if "like_count" in m]
    return statistics.median(counts) if len(counts) >= MIN_BASELINE_POSTS else None


def fetch_creator(username: str, config: dict, now: datetime, stats: dict) -> dict:
    """Business Discovery for one username → {username, followers, media}. Cached 6 h."""
    cache_key = f"ig_bd_{username}_{now.strftime('%Y-%m-%d')}"
    cached = _load_cache(cache_key)
    if cached is not None:
        print(f"  [cache] business discovery @{username}")
        return cached
    fields = (f"business_discovery.username({username})"
              f"{{username,followers_count,media_count,"
              f"media.limit({BD_MEDIA_LIMIT}){{{MEDIA_FIELDS}}}}}")
    body = _graph_get(config["user_id"], {"fields": fields}, config, stats)
    bd = body.get("business_discovery", {})
    data = {
        "username": bd.get("username", username),
        "followers": bd.get("followers_count"),
        "media": bd.get("media", {}).get("data", []),
    }
    _save_cache(cache_key, data)
    return data


def collect_creator_posts(creators: list[str], config: dict, now: datetime,
                          stats: dict) -> list[dict]:
    cutoff = now - timedelta(days=SEARCH_PUBLISHED_DAYS)
    posts: list[dict] = []
    stats.setdefault("failed_creators", {})
    for username in creators:
        try:
            data = fetch_creator(username, config, now, stats)
        except _ItemError as e:
            stats["failed_creators"][username] = str(e)
            print(f"[Instagram] @{username} skipped — {e}")
            continue
        baseline = creator_baseline(data["media"])
        usable = [m for m in data["media"] if _usable(m, cutoff)]
        posts.extend(_post(m, data["username"].lower(), data["followers"], baseline,
                           "business_discovery") for m in usable)
        print(f"[Instagram] @{username}: {len(data['media'])} posts fetched, "
              f"{len(usable)} usable Reels in {SEARCH_PUBLISHED_DAYS}d, baseline={baseline}")
    stats["creators_ok"] = len(creators) - len(stats["failed_creators"])
    return posts


# ─── Hashtag Search ────────────────────────────────────────────────────────────

def hashtags_from_queries(queries: list[str]) -> list[str]:
    """'morning routine tips' → 'morningroutinetips' (Instagram hashtags have no spaces)."""
    tags = [re.sub(r"[^a-z0-9_]", "", q.lower()) for q in queries]
    return list(dict.fromkeys(t for t in tags if 3 <= len(t) <= 40))


def _load_usage(now: datetime) -> dict[str, str]:
    try:
        usage = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        usage = {}
    week_ago = now - timedelta(days=7)
    return {tag: ts for tag, ts in usage.items()
            if datetime.fromisoformat(ts) >= week_ago}


def _save_usage(usage: dict[str, str]) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        USAGE_FILE.write_text(json.dumps(usage, indent=2), encoding="utf-8")
    except OSError:
        pass


def reserve_hashtags(tags: list[str], now: datetime) -> tuple[list[str], list[str]]:
    """
    Keep the run inside Meta's 30-unique-hashtags-per-7-days limit.
    Tags already searched this week are free; new ones use up a slot.
    Returns (allowed, skipped).
    """
    usage = _load_usage(now)
    allowed, skipped = [], []
    for tag in tags:
        if tag in usage or len(usage) < HASHTAG_WEEKLY_LIMIT:
            usage.setdefault(tag, now.isoformat())
            allowed.append(tag)
        else:
            skipped.append(tag)
    _save_usage(usage)
    return allowed, skipped


def release_hashtags(tags: list[str], now: datetime) -> None:
    """Give back slots for tags that were never actually searched."""
    usage = _load_usage(now)
    for tag in tags:
        usage.pop(tag, None)
    _save_usage(usage)


def _is_access_error(message: str) -> bool:
    """Hashtag Search needs 'Instagram Public Content Access' (App Review)."""
    return "code=10" in message or "Public Content Access" in message


def fetch_hashtag_media(tag: str, config: dict, now: datetime, stats: dict) -> list[dict]:
    """ig_hashtag_search → top_media + recent_media. Cached 6 h."""
    cache_key = f"ig_tag_{tag}_{now.strftime('%Y-%m-%d')}"
    cached = _load_cache(cache_key)
    if cached is not None:
        print(f"  [cache] hashtag #{tag}")
        return cached
    found = _graph_get("ig_hashtag_search", {"user_id": config["user_id"], "q": tag},
                       config, stats).get("data", [])
    if not found:
        return []
    media: list[dict] = []
    for edge in ("top_media", "recent_media"):
        body = _graph_get(f"{found[0]['id']}/{edge}", {
            "user_id": config["user_id"], "fields": HASHTAG_MEDIA_FIELDS,
            "limit": HASHTAG_MEDIA_LIMIT}, config, stats)
        media.extend(body.get("data", []))
    _save_cache(cache_key, media)
    return media


def collect_hashtag_posts(tags: list[str], config: dict, now: datetime,
                          stats: dict) -> list[dict]:
    cutoff = now - timedelta(days=SEARCH_PUBLISHED_DAYS)
    allowed, skipped = reserve_hashtags(tags[:MAX_HASHTAGS_PER_RUN], now)
    stats["hashtags_used"] = allowed
    if skipped:
        stats["hashtags_skipped_weekly_limit"] = skipped
        print(f"[Instagram] Weekly hashtag limit reached — skipped {skipped}")
    posts: list[dict] = []
    for i, tag in enumerate(allowed):
        try:
            media = fetch_hashtag_media(tag, config, now, stats)
        except _ItemError as e:
            if _is_access_error(str(e)):
                # App-level: no tag will work, so stop and give the slots back.
                release_hashtags(allowed[i:], now)
                stats["hashtags_used"] = allowed[:i]
                stats["hashtag_access"] = "unavailable: needs App Review (Instagram Public Content Access)"
                print("[Instagram] Hashtag Search not available for this app "
                      "(needs App Review) — continuing with creators only")
                break
            stats.setdefault("failed_hashtags", {})[tag] = str(e)
            print(f"[Instagram] #{tag} skipped — {e}")
            continue
        usable = [m for m in media if _usable(m, cutoff)]
        # Unknown author: empty channel_id keeps them out of creator counts.
        posts.extend({**_post(m, "", None, None, f"hashtag:#{tag}"), "channel": f"#{tag}",
                      "channel_id": ""} for m in usable)
        print(f"[Instagram] #{tag}: {len(media)} posts, {len(usable)} usable")
    return posts


# ─── Entry point used by research_agent.run_research ──────────────────────────

def collect_posts(queries: list[str], config: dict, now: datetime) -> tuple[list[dict], dict]:
    """
    All usable Reels from the creator list + hashtags, deduplicated by media id
    (a creator's own copy wins over the anonymous hashtag copy).

    Raises:
        InstagramAPIError: token/permission problem — nothing can be fetched.
    """
    stats: dict[str, Any] = {"api_calls": 0}
    creator_posts = collect_creator_posts(config["creators"], config, now, stats)
    if not stats["creators_ok"]:
        raise InstagramAPIError(
            f"no creator could be looked up: {stats['failed_creators']}")
    tags = config.get("hashtags") or hashtags_from_queries(queries)
    hashtag_posts = collect_hashtag_posts(tags, config, now, stats)

    seen = {p["video_id"] for p in creator_posts}
    posts = creator_posts + [p for p in hashtag_posts if p["video_id"] not in seen
                             and not seen.add(p["video_id"])]
    stats.update({
        "posts_from_creators": len(creator_posts),
        "posts_from_hashtags": len(posts) - len(creator_posts),
        "api_cost": f"{stats['api_calls']} Graph API calls (free)",
    })
    print(f"[Instagram] {len(creator_posts)} creator Reels + "
          f"{stats['posts_from_hashtags']} hashtag Reels")
    return posts, stats
