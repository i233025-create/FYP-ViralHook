"""
research_agent.py — LangGraph Research Agent Node
==================================================
Finds what is trending in the creator's niche RIGHT NOW from real platform
data. Every number in the output comes from real posts; the local LLM only
does language work (queries, names, explanations).

Two data sources, chosen with TREND_SOURCE (or run_research(source=...)):
  youtube    (V1)  YouTube Data API v3 — Shorts search. Code in this file.
  instagram  (V2)  Instagram Graph API — Business Discovery for a list of
                   niche creators + Hashtag Search. See instagram_source.py.
Both sources return posts in the same shape, so steps [3]–[6] — including
the trend definition — are shared and the two versions compare fairly.

Flow:
  [1] Query generation   local LLM turns the creator profile into 5 short
                         search-bar queries (fallback: recurring_topics + niche).
  [2] Discovery          youtube: search.list twice per query — last 14 days
                         and last 3 days (order=viewCount favours old videos,
                         so the 3-day search keeps the growth check honest)
                         → videos.list (stats + duration, keep ≤ 180 s)
                         → channels.list (subscriber counts + uploads playlist)
                         → playlistItems.list per channel (latest 30 uploads)
                           → channel's median views of its older Shorts
                           (cached a week).
                         Daily view snapshots (trend_snapshots.py): every
                         run stores each video's views and re-reads the
                         videos tracked in the last 8 days.
                         Drops hashtag-only titles and non-Latin-script
                         titles or channel names.
  [3] Scoring            outlier    youtube: views / max(channel's median
                                    Shorts views, 5000); fallback when the
                                    channel has < 5 older Shorts:
                                    views / max(subs, 5000)
                                    instagram: (likes+comments) / creator's
                                    median (likes+comments) — its real normal
                         velocity   = views (IG: likes+comments) / hour
                         engagement = (likes + comments) / views (IG: / followers)
                         log-scale → min-max → weighted video_score.
  [4] Clustering         all-MiniLM-L6-v2 embeddings of the cleaned title
                         (tags are hashtag spam) → near-duplicates collapsed
                         → AgglomerativeClustering (cosine, complete).
  [5] Trend definition   docs/trend_sources_comparison.pdf, section 3.
                         Clusters with creator_fit < 0.45 are dropped. Each
                         remaining cluster gets 4 checks:
                           overperforms  median outlier ≥ 1.5
                           growing       measured (≥ 2 posts seen in an
                                         earlier snapshot): median view
                                         acceleration ÷ the niche's ≥ 1.3.
                                         Otherwise estimated: relative_growth
                                         ≥ 1.3, the cluster's upload rate
                                         (last 3 days vs the 11 before) ÷ the
                                         whole niche's
                           spreading     ≥ 3 distinct creators
                           recent        median age ≤ 14 days
                         and a trend_type:
                           trend          all four pass, growth measured
                                          (estimate only → emerging)
                           emerging       overperforms + growing, 2 creators
                           evergreen      spreading, not growing
                           topic          anything else with ≥ 2 creators
                           one_off_viral  overperforms, 1 creator  (hidden)
                         Ranked by type, then 0.35 strength + 0.20 growth +
                         0.15 spread + 0.30 creator_fit. Only "trend" is
                         high confidence.
  [6] Labeling           local LLM names each top cluster and explains it.
                         Never outputs numbers. Fallback: cleaned top title.

Fallback:
  If the source's credentials are missing or the API fails, the node returns
  the creator's first recurring topic with trend_score 0 and low_confidence,
  plus research_error. Scores are never invented. The graph never crashes.

YouTube quota cost per full run:
  search.list   = 100 units × 5 queries × 2 windows = 1,000 units
  videos.list   = 1 unit per 50 IDs                 ≈ 6 units
  channels.list = 1 unit per 50 IDs                 ≈ 5 units
  baselines     = 1 unit per new channel + 1 per 50 videos ≈ 150–250 units
                  on a cold cache, ~0 when the week-long cache is warm
  snapshots     = 1 unit per 50 tracked videos      ≈ 5–30 units
  Total         ≈ 1,050–1,300 units / run  (free quota 10,000/day)
  Search results are cached in pipeline/cache/ for 6 hours.

Thresholds can be overridden from .env (e.g. TREND_GROWTH_RATIO_MIN=1.5)
without touching code; see _env_number().
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import statistics
import sys
import unicodedata
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import requests
from dotenv import load_dotenv
from sklearn.cluster import AgglomerativeClustering

# Load .env — check both locations
load_dotenv(Path(__file__).parent.parent.parent / "module1_style_extraction" / ".env")
load_dotenv(Path(__file__).parent.parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from pipeline.state import PipelineState  # noqa: E402
from pipeline.local_llm import LocalLLMError, chat_json  # noqa: E402
from pipeline.embeddings import embed_texts  # noqa: E402,F401  (module attr: tests patch it)
from pipeline.embeddings import MULTILINGUAL_EMBEDDING_MODEL  # noqa: E402
from pipeline.agents import trend_snapshots as snapshots  # noqa: E402

# ─── Configuration ─────────────────────────────────────────────────────────────

def _env_number(name: str, default: float) -> float:
    """Threshold from .env (TREND_<NAME>), falling back to the default."""
    raw = os.getenv(f"TREND_{name}", "")
    try:
        return type(default)(raw) if raw.strip() else default
    except ValueError:
        print(f"[ResearchAgent] Ignoring bad TREND_{name}={raw!r}")
        return default


CACHE_DIR = Path(__file__).parent.parent / "cache"
CACHE_TTL_HOURS = 6

MAX_QUERIES = 5
SEARCH_MAX_RESULTS = 50          # per query (API maximum)
SEARCH_PUBLISHED_DAYS = 14       # only videos uploaded in the last N days
RELEVANCE_LANGUAGE = "en"
MAX_SHORT_SECONDS = 180          # YouTube Shorts can be up to 3 minutes
MIN_VIEWS = 1000                 # ignore videos with no real traction yet
# Outlier = views / max(subscribers, floor). At 1000, a 0-subscriber channel with
# 1,500 views scored 1.5× and passed "overperforms" (E1 fitness: generic
# "subscribe / transform your body" Shorts from 0–98-sub channels became a trend).
# At 5000 such a channel needs 7,500+ views to reach 1.5×.
SUBSCRIBER_FLOOR = _env_number("SUBSCRIBER_FLOOR", 5000)
# Channel baseline: "over-performs" = views ÷ the channel's own median Shorts
# views (its real normal), not ÷ subscribers. Subscribers are only the
# fallback when the channel has too few older Shorts.
CHANNEL_BASELINE = bool(_env_number("CHANNEL_BASELINE", 1))
VIEW_BASELINE_FLOOR = _env_number("VIEW_BASELINE_FLOOR", 5000)   # outlier = views / max(median, this)
BASELINE_UPLOADS = 30            # latest uploads read per channel (playlistItems, 1 unit)
BASELINE_MIN_AGE_DAYS = 3        # younger uploads are still gaining views: left out
BASELINE_MIN_VIDEOS = 5          # fewer older Shorts than this → subscriber fallback
BASELINE_TTL_HOURS = 24 * 7      # a channel's normal changes slowly: cache a week

MIN_TITLE_WORDS = 3              # after hashtags/emoji are stripped
MIN_LATIN_RATIO = 0.7            # drops Devanagari/Urdu titles with no language tag
MAX_NON_LATIN_LETTERS = 1        # titles: more letters than this from another script
                                 # ("Motivation नहीं, Discipline…" is 78 % Latin) are dropped
# Romanised non-English titles ("Jeevitha satyalu…", "Zindagi badal degi…") are
# Latin script, so they pass the check above. They are caught by the share of
# words that are common English words. langdetect was tried first and rejected:
# on short titles it called "Train Smarter, Build Stronger!" German and the
# Telugu title English. On the E1 titles: English ≥ 0.67, Hinglish/Telugu ≤ 0.57.
MIN_ENGLISH_WORD_SHARE = _env_number("MIN_ENGLISH_WORD_SHARE", 0.6)
ENGLISH_WORD_ZIPF = 3.0          # wordfreq Zipf ≥ this = common English word
# English titles over non-English content ("motivation quotes in hindi",
# "motivational quotes Kannada #kannada") pass both checks above. When the
# title, a hashtag or a tag names another language, the video is dropped.
NON_ENGLISH_LANGUAGE_WORDS = {
    "hindi", "urdu", "punjabi", "bengali", "bangla", "marathi", "gujarati",
    "tamil", "telugu", "kannada", "malayalam", "odia", "nepali", "sinhala",
    "bhojpuri", "haryanvi", "assamese", "pashto", "sindhi", "mizo",
    "arabic", "spanish", "espanol", "español", "portuguese", "french",
    "german", "turkish", "indonesian", "tagalog", "filipino", "russian",
}

# Video score weights (step 3)
W_OUTLIER, W_VELOCITY, W_ENGAGEMENT = 0.45, 0.35, 0.20

# Clustering (step 4)
CLUSTER_LINKAGE = "complete"      # every pair in a cluster must be similar
# cosine distance; lower = tighter clusters. 0.6 mixed nearby sub-topics in E1
# ("exercises after 60" + "high-protein foods"), so 0.5 (experiments/trend_e1/REPORT.md §4)
CLUSTER_DISTANCE_THRESHOLD = _env_number("CLUSTER_DISTANCE", 0.5)
DUPLICATE_SIMILARITY = 0.95       # cosine ≥ this = same video reuploaded
MIN_WEAK_CLUSTER_SIZE = 2         # smallest cluster that can be shown at all
MIN_CLUSTER_CHANNELS = 2          # fewer creators = one creator's series, not a trend
MIN_CREATOR_FIT = 0.45            # cosine vs recurring_topics; below = outside the niche
# The multilingual model (Urdu niches) spreads cosines differently, so its
# thresholds are set separately (calibrated on E1 data, see REPORT.md section 18).
MULTILINGUAL_CLUSTER_DISTANCE = _env_number("MULTILINGUAL_CLUSTER_DISTANCE", 0.44)
MULTILINGUAL_MIN_CREATOR_FIT = _env_number("MULTILINGUAL_MIN_CREATOR_FIT", 0.50)

# Trend definition (step 5) — docs/trend_sources_comparison.pdf, section 3
OVERPERFORM_OUTLIER = _env_number("OVERPERFORM_OUTLIER", 1.5)   # median outlier ≥ this
GROWTH_RATIO_MIN = _env_number("GROWTH_RATIO_MIN", 1.3)         # recent vs earlier upload rate
MIN_TREND_CHANNELS = _env_number("MIN_TREND_CHANNELS", 3)       # "spreading"
RECENT_WINDOW_DAYS = _env_number("RECENT_WINDOW_DAYS", 3)       # "growing" compares this window…
GROWTH_SMOOTHING = 0.5            # …with the rest; +0.5/day stops 0-division and 1-video spikes
GROWTH_PRIOR_POSTS = 2            # relative growth: pseudo-posts at the niche's recent share
# Measured growth from daily view snapshots (trend_snapshots.py). When a
# cluster has ≥ MIN_MEASURED_MEMBERS videos seen in an earlier snapshot,
# "growing" = its median view acceleration ÷ the niche's ≥ GROWTH_RATIO_MIN.
# Otherwise growth falls back to the upload-rate estimate, and (with
# REQUIRE_MEASURED_GROWTH) a cluster passing all checks is only "emerging".
SNAPSHOTS = bool(_env_number("SNAPSHOTS", 1))
SNAPSHOT_DIR = Path(__file__).parent.parent / "cache" / "snapshots"
MIN_MEASURED_MEMBERS = 2
REQUIRE_MEASURED_GROWTH = bool(_env_number("REQUIRE_MEASURED_GROWTH", 1))

TYPE_RANK = {"trend": 0, "emerging": 1, "evergreen": 2, "topic": 3}
HIDDEN_TYPES = {"one_off_viral", "single_creator"}

# Trend score weights (step 5) — strength leads so fit can't lift a dead topic
W_STRENGTH, W_GROWTH, W_SPREAD, W_FIT = 0.35, 0.20, 0.15, 0.30
GROWTH_SCORE_CAP = 4.0            # growth_ratio at or above this scores 1.0

TOP_K_TRENDS = 5
EVIDENCE_PER_TREND = 5
TITLES_FOR_LABELING = 8

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
YOUTUBE_PLAYLIST_ITEMS_URL = "https://www.googleapis.com/youtube/v3/playlistItems"


# ─── Cache Utilities ───────────────────────────────────────────────────────────

def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{hashlib.md5(key.encode()).hexdigest()}.json"


def _load_cache(key: str, ttl_hours: float = CACHE_TTL_HOURS) -> Any | None:
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            cached = json.load(f)
        cached_at = datetime.fromisoformat(cached.get("cached_at", "2000-01-01"))
        if datetime.now() - cached_at > timedelta(hours=ttl_hours):
            return None
        return cached.get("data")
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def _save_cache(key: str, data: Any) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(_cache_path(key), "w", encoding="utf-8") as f:
            json.dump({"cached_at": datetime.now().isoformat(), "data": data}, f, indent=2)
    except IOError:
        pass


# ─── Text Helpers ──────────────────────────────────────────────────────────────

_NOISE_WORDS = {"shorts", "short", "shortsfeed", "viral", "trending", "reels",
                "reel", "tiktok", "youtube", "subscribe", "fyp", "foryou"}


def _clean_text(text: str) -> str:
    """Strip URLs, hashtags, emoji and noise words from a title/description."""
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"#\w+", " ", text)
    text = re.sub(r"[^\w\s'’,.!?-]", " ", text)   # drops emoji and symbols
    text = text.replace("_", " ")
    words = [w for w in text.split() if w.lower().strip(".,!?") not in _NOISE_WORDS]
    return re.sub(r"\s+", " ", " ".join(words)).strip(" -,.")


def _clean_topic_phrase(text: str) -> str:
    """'Personal growth & self‑comparison' → 'personal growth self comparison'."""
    text = re.sub(r"[&/‑–—-]", " ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


# ─── [1] Query Generation ──────────────────────────────────────────────────────

def _fallback_queries(profile: dict, niche: str) -> list[str]:
    """Deterministic queries straight from the creator profile."""
    queries = [_clean_topic_phrase(t) for t in profile.get("recurring_topics", [])]
    if niche:
        queries.append(" ".join(_clean_topic_phrase(niche).split()[:5]))
    seen: set[str] = set()
    unique = []
    for q in queries:
        if q and q not in seen:
            seen.add(q)
            unique.append(q)
    return unique[:MAX_QUERIES]


def generate_queries(profile: dict, niche: str) -> list[str]:
    """
    Ask the local LLM for specific YouTube search queries based on the
    creator profile. Tops up with profile-based queries if the LLM fails
    or returns too few.
    """
    fallback = _fallback_queries(profile, niche)
    prompt = (
        "You help a short-form video creator find trending topics on YouTube Shorts.\n"
        f"Niche: {niche}\n"
        f"Recurring topics: {json.dumps(profile.get('recurring_topics', []), ensure_ascii=False)}\n"
        f"Target audience: {profile.get('target_audience', 'unknown')}\n\n"
        f"Write {MAX_QUERIES} YouTube search queries this audience types into the search bar.\n"
        "Rules:\n"
        "- 2-4 simple everyday words, exactly how people search\n"
        "- no colons, quotes or punctuation\n"
        "- each query about a different sub-topic of this niche\n"
        "Style examples from OTHER niches: 'budget meal prep', 'gym beginner mistakes', "
        "'iphone camera tips'.\n"
        'Return JSON: {"queries": ["...", "..."]}'
    )
    try:
        result = chat_json(prompt, temperature=0.4, max_tokens=200)
        raw = result.get("queries", [])
        llm_queries = [
            q.strip().lower() for q in raw
            if isinstance(q, str) and 2 <= len(q.split()) <= 5 and len(q) <= 50
            and not re.search(r"[:;\"()]", q)
        ]
    except LocalLLMError as e:
        print(f"[ResearchAgent] Query LLM unavailable — using profile queries ({e})")
        llm_queries = []

    queries = list(dict.fromkeys(llm_queries))[:MAX_QUERIES]
    for q in fallback:
        if len(queries) >= MAX_QUERIES:
            break
        if q not in queries:
            queries.append(q)
    return queries


# ─── [2] Discovery (YouTube Data API) ──────────────────────────────────────────

YOUTUBE_QUOTA_USED = {"units": 0}    # reset per run; reported in run stats


def _published_after_iso(now: datetime, days: float = SEARCH_PUBLISHED_DAYS) -> str:
    cutoff = now - timedelta(days=days)
    return cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")


def _search_video_ids(query: str, api_key: str, now: datetime,
                      days: float = SEARCH_PUBLISHED_DAYS,
                      relevance_language: str = RELEVANCE_LANGUAGE) -> list[str]:
    """search.list — 100 quota units per call. Cached for CACHE_TTL_HOURS."""
    lang_part = "" if relevance_language == RELEVANCE_LANGUAGE else f"_{relevance_language}"
    cache_key = f"search_v3_{query}_{days}d{lang_part}_{now.strftime('%Y-%m-%d')}"
    cached = _load_cache(cache_key)
    if cached is not None:
        print(f"  [cache] search results for '{query}' ({days}d)")
        return cached

    YOUTUBE_QUOTA_USED["units"] += 100
    response = requests.get(YOUTUBE_SEARCH_URL, params={
        "part": "id",
        "q": query,
        "type": "video",
        "videoDuration": "short",          # < 4 min; exact ≤ 180 s filter below
        "publishedAfter": _published_after_iso(now, days),
        "relevanceLanguage": relevance_language,
        "order": "viewCount",              # outlier score removes big-channel bias
        "maxResults": SEARCH_MAX_RESULTS,
        "key": api_key,
    }, timeout=15)
    response.raise_for_status()

    ids = [item["id"]["videoId"] for item in response.json().get("items", [])
           if item.get("id", {}).get("videoId")]
    _save_cache(cache_key, ids)
    return ids


def parse_iso_duration(duration: str) -> int:
    """ISO 8601 duration ('PT1M5S') → seconds. Returns 0 if unparseable."""
    match = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration or "")
    if not match:
        return 0
    days, hours, minutes, seconds = (int(g) if g else 0 for g in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def _batched_get(url: str, ids: list[str], part: str, api_key: str) -> list[dict]:
    """videos.list / channels.list in batches of 50 IDs (1 unit per batch)."""
    items: list[dict] = []
    for i in range(0, len(ids), 50):
        YOUTUBE_QUOTA_USED["units"] += 1
        response = requests.get(url, params={
            "part": part, "id": ",".join(ids[i:i + 50]), "key": api_key,
        }, timeout=15)
        response.raise_for_status()
        items.extend(response.json().get("items", []))
    return items


def _fetch_video_details(video_ids: list[str], api_key: str) -> list[dict]:
    """Stats, snippet and duration for each video, flattened."""
    videos = []
    for item in _batched_get(YOUTUBE_VIDEOS_URL, video_ids,
                             "snippet,statistics,contentDetails", api_key):
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        videos.append({
            "video_id": item["id"],
            "title": " ".join(snippet.get("title", "").split()),
            "description": snippet.get("description", "")[:300],
            "tags": snippet.get("tags", [])[:10],
            "channel": " ".join(snippet.get("channelTitle", "").split()),
            "channel_id": snippet.get("channelId", ""),
            "language": snippet.get("defaultAudioLanguage") or snippet.get("defaultLanguage") or "",
            "published_at": snippet.get("publishedAt", ""),
            "duration_s": parse_iso_duration(item.get("contentDetails", {}).get("duration", "")),
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "comments": int(stats.get("commentCount", 0)),
            "platform": "youtube",
            "url": f"https://www.youtube.com/shorts/{item['id']}",
        })
    return videos


def _fetch_channel_info(channel_ids: list[str], api_key: str) -> dict[str, dict]:
    """
    channel_id → {"subscribers": int | None (hidden), "uploads": playlist id}.
    Same cost as subscribers alone: contentDetails comes in the same call.
    """
    info: dict[str, dict] = {}
    for item in _batched_get(YOUTUBE_CHANNELS_URL, channel_ids, "statistics,contentDetails", api_key):
        stats = item.get("statistics", {})
        hidden = stats.get("hiddenSubscriberCount", False)
        info[item["id"]] = {
            "subscribers": None if hidden else int(stats.get("subscriberCount", 0)),
            "uploads": item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads", ""),
        }
    return info


def _fetch_subscribers(channel_ids: list[str], api_key: str) -> dict[str, int | None]:
    """channel_id → subscriber count (None when the channel hides it)."""
    return {cid: x["subscribers"] for cid, x in _fetch_channel_info(channel_ids, api_key).items()}


def _recent_upload_ids(playlist_id: str, api_key: str) -> list[tuple[str, str]]:
    """(video_id, published_at) of a channel's latest uploads. 1 quota unit."""
    YOUTUBE_QUOTA_USED["units"] += 1
    response = requests.get(YOUTUBE_PLAYLIST_ITEMS_URL, params={
        "part": "contentDetails", "playlistId": playlist_id,
        "maxResults": BASELINE_UPLOADS, "key": api_key,
    }, timeout=15)
    response.raise_for_status()
    return [(it["contentDetails"]["videoId"], it["contentDetails"].get("videoPublishedAt", ""))
            for it in response.json().get("items", []) if it.get("contentDetails", {}).get("videoId")]


def _fetch_channel_baselines(uploads: dict[str, str], api_key: str, now: datetime,
                             exclude_ids: set[str]) -> dict[str, float | None]:
    """
    channel_id → median views of the channel's older Shorts (≤ MAX_SHORT_SECONDS,
    ≥ BASELINE_MIN_AGE_DAYS old, not in this run's results), or None when
    it has fewer than BASELINE_MIN_VIDEOS. Cached per channel for a week.
    Cost on a cold cache: 1 unit per channel + 1 per 50 baseline videos.
    """
    baselines: dict[str, float | None] = {}
    todo: dict[str, list[str]] = {}
    cutoff = now - timedelta(days=BASELINE_MIN_AGE_DAYS)
    for cid, playlist in uploads.items():
        cached = _load_cache(f"baseline_v1_{cid}", ttl_hours=BASELINE_TTL_HOURS)
        if cached is not None:
            baselines[cid] = cached.get("median")
            continue
        if not playlist:
            baselines[cid] = None
            continue
        try:
            items = _recent_upload_ids(playlist, api_key)
        except requests.RequestException:
            baselines[cid] = None      # private/removed playlist: subscriber fallback
            continue
        todo[cid] = [vid for vid, pub in items
                     if vid not in exclude_ids and (_parse_utc(pub) or now) <= cutoff]

    all_ids = list(dict.fromkeys(vid for ids in todo.values() for vid in ids))
    details: dict[str, dict] = {}
    if all_ids:
        for item in _batched_get(YOUTUBE_VIDEOS_URL, all_ids, "statistics,contentDetails", api_key):
            details[item["id"]] = {
                "views": int(item.get("statistics", {}).get("viewCount", 0)),
                "duration_s": parse_iso_duration(item.get("contentDetails", {}).get("duration", "")),
            }
    for cid, ids in todo.items():
        views = [details[v]["views"] for v in ids
                 if v in details and 0 < details[v]["duration_s"] <= MAX_SHORT_SECONDS]
        median = float(statistics.median(views)) if len(views) >= BASELINE_MIN_VIDEOS else None
        baselines[cid] = median
        _save_cache(f"baseline_v1_{cid}", {"median": median, "shorts": len(views)})
    return baselines


def _fetch_view_counts(video_ids: list[str], api_key: str) -> dict[str, int]:
    """video_id → current views (1 unit per 50 IDs). For snapshot tracking."""
    return {item["id"]: int(item.get("statistics", {}).get("viewCount", 0))
            for item in _batched_get(YOUTUBE_VIDEOS_URL, video_ids, "statistics", api_key)}


def _parse_utc(ts: str) -> datetime | None:
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _non_latin_letters(text: str) -> int:
    """Letters from scripts other than Latin (accented Latin letters count as Latin)."""
    return sum(1 for c in text if c.isalpha() and not c.isascii()
               and not unicodedata.name(c, "").startswith("LATIN"))


def _latin_ratio(text: str, if_no_letters: float = 0.0) -> float:
    """Share of letters that are ASCII (Latin script)."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return if_no_letters
    return sum(c.isascii() for c in letters) / len(letters)


_zipf_frequency: Callable[[str, str], float] | None | bool = False   # False = not loaded yet


def english_word_share(text: str) -> float | None:
    """
    Share of the words in `text` that are common English words (wordfreq).
    None when wordfreq is not installed (the check is then skipped) or the
    text has no words.
    """
    global _zipf_frequency
    if _zipf_frequency is False:
        try:
            from wordfreq import zipf_frequency
            _zipf_frequency = zipf_frequency
        except ImportError:
            print("[ResearchAgent] wordfreq not installed — skipping the English-words check")
            _zipf_frequency = None
    if _zipf_frequency is None:
        return None
    words = [w for w in re.findall(r"[A-Za-z]+", text) if len(w) > 1 or w.lower() in ("a", "i")]
    if not words:
        return None
    return sum(_zipf_frequency(w.lower(), "en") >= ENGLISH_WORD_ZIPF for w in words) / len(words)


def _title_is_informative(title: str) -> bool:
    """
    Hashtag-only titles ('#motivation #shorts') carry no topic signal and
    all look alike once cleaned; non-Latin titles slip past missing
    language tags, and romanised non-English titles ('Zindagi badal degi
    ye baat') slip past the script check. All are dropped.
    """
    cleaned = _clean_text(title)
    if len(cleaned.split()) < MIN_TITLE_WORDS or _latin_ratio(cleaned) < MIN_LATIN_RATIO:
        return False
    if _non_latin_letters(title) > MAX_NON_LATIN_LETTERS:
        return False
    share = english_word_share(cleaned)
    return share is None or share >= MIN_ENGLISH_WORD_SHARE


def names_other_language(video: dict, allowed: set[str] = frozenset()) -> bool:
    """
    True when the title, its hashtags or the tags name a language that is
    not English and not in `allowed` (e.g. {"urdu"} for Urdu niches).
    """
    names = NON_ENGLISH_LANGUAGE_WORDS - set(allowed)
    text = " ".join([video.get("title", ""), *video.get("tags", [])]).lower()
    words = set(re.findall(r"[^\W\d_]+", text))
    # hashtags like #hindimotivation / #kannadaquotes: check the word starts too
    hashtags = re.findall(r"#([^\W_]+)", text)
    return bool(words & names) or any(
        tag.startswith(lang) for tag in hashtags for lang in names)


# ── Urdu (Urdu script + Roman Urdu), opt-in per niche: languages=("en", "ur") ──
# Urdu and Arabic share one script. Letters only Urdu uses mark a title as
# Urdu; letters only Arabic uses (or none of the Urdu ones) mark it Arabic,
# which stays out. Persian is rare in this data and also stays out.
URDU_ONLY_LETTERS = set("ٹڈڑںےۓھہ")
URDU_LIKELY_LETTERS = set("یکگچپ")          # Urdu/Persian forms; Arabic writes ي ك
ARABIC_ONLY_LETTERS = set("ةيكىأإ")      # not ئ / آ / ؤ: Urdu uses them (سچائی, آپ)
# Roman Urdu and Roman Hindi are the same language in Latin letters, except
# for vocabulary. A title counts as Roman Urdu when ≥ ROMAN_URDU_MIN_WORDS of
# its words are common Roman Urdu words. Clearly Hindi/Sanskrit vocabulary or
# Hindu devotional content keeps it out (the niche asked for Urdu, not Hindi).
ROMAN_URDU_WORDS = {
    "hai", "hain", "ho", "hota", "hoti", "hote", "tha", "thi", "the", "ka", "ki", "ke", "ko",
    "se", "mein", "mai", "par", "pe", "aur", "ya", "nahi", "nahin", "na", "kya", "kyun", "kyon",
    "kaise", "kaisa", "kab", "kahan", "jab", "tab", "agar", "lekin", "magar", "sirf", "bas",
    "bhi", "hi", "ye", "yeh", "wo", "woh", "is", "us", "un", "in", "apna", "apni", "apne",
    "mera", "meri", "mere", "tera", "teri", "tere", "hum", "tum", "aap", "ap", "sab", "kuch",
    "koi", "bohat", "bohot", "bahut", "zyada", "ziada", "kam", "acha", "achha", "achi", "bura",
    "bari", "bara", "bada", "chota", "choti", "naya", "nayi", "pehle", "pehla", "baad", "ab",
    "abhi", "kabhi", "hamesha", "zaroor", "zarur", "karo", "karein", "karen", "karna", "karne",
    "kar", "kiya", "kiye", "raha", "rahi", "rahe", "gaya", "gayi", "jao", "jana", "jata", "jati",
    "dekho", "dekhain", "suno", "samjho", "socho", "banao", "banaye", "seekho", "lo", "do", "dena",
    "zindagi", "zindgi", "dil", "mohabbat", "muhabbat", "ishq", "khuda", "allah", "dua", "sabr",
    "shukar", "kamyabi", "kamiyabi", "mehnat", "himmat", "waqt", "insan", "insaan", "log", "logon",
    "duniya", "dunya", "baat", "baatein", "batein", "din", "raat", "subah", "sham", "khana",
    "ghar", "paisa", "paise", "kaam", "dost", "yaar", "bhai", "behen", "ammi", "abbu", "maa",
    "jaldi", "asaan", "aasan", "tareeqa", "tarika", "nuskha", "sehat", "wazan", "pet", "chehra",
    "khubsurat", "behtareen", "zabardast", "mazedar", "lazeez", "recipe", "wala", "wali", "wale",
    "chahiye", "chahie", "lena", "lene", "leni", "dene", "deni", "milta", "milti", "milega",
    "sakte", "sakta", "sakti", "hoga", "hogi", "honge", "banaen", "khao", "khayen", "piyo",
    "peena", "rakho", "chhodo", "chodo", "chalo", "aao", "jaise", "aadat", "aadatein", "faide",
    "fayde", "nuqsan", "nuksan", "tarah", "sahi", "galat", "ghalat", "pura", "poora", "shuru",
    "khatam", "jism", "badan", "taqat", "kamzori", "subha", "kitna", "kitni", "kyu",
    "sabse", "banane", "banayein", "banaein", "banao", "aasani", "asani", "mazedaar", "chatpati",
    "jaan", "dawat", "tarike", "tareeke", "roti", "ghussa", "beti", "beta", "bache", "bachon",
    "khane", "pakane", "pakana", "liye", "wali", "ki", "baare", "bare", "sach", "jhoot", "seekh",
}
HINDI_MARKER_WORDS = {
    "jeevan", "safalta", "samay", "vishwas", "sangharsh", "prerna", "gyan", "vichar",
    "suvichar", "anmol", "shiksha", "bhagwan", "ishwar", "prabhu", "mahadev", "krishna",
    "radhe", "hanuman", "pravachan", "maharaj", "bhajan", "mandir", "sanatan", "shri",
    "shree", "jai", "namaste", "dhanyavad", "kripya", "atma", "dharm", "karm",
}
ROMAN_URDU_MIN_WORDS = 2
MIN_KNOWN_WORD_SHARE = 0.6        # Roman Urdu: share of words that are English or Roman Urdu…
MIN_ROMAN_URDU_SHARE = 0.3        # …or share of words that are Roman Urdu (dish/place names)
# YouTube tags much Pakistani Roman Urdu content "hi" (Hindustani). In Urdu
# niches a "hi" tag is accepted when the title itself is Urdu / Roman Urdu
# (Devanagari and Hindi vocabulary are still dropped by title_language).
AMBIGUOUS_TAGS_FOR_URDU = ("hi",)
DEFAULT_LANGUAGES = tuple(x.strip() for x in os.getenv("TREND_LANGUAGES", "en").split(",") if x.strip())


def _arabic_script_letters(text: str) -> list[str]:
    return [c for c in text if c.isalpha() and "ARABIC" in unicodedata.name(c, "")]


def _is_urdu_script(text: str) -> bool:
    """Arabic-script text that is Urdu (not Arabic). See URDU_ONLY_LETTERS."""
    letters = set(_arabic_script_letters(text))
    if letters & URDU_ONLY_LETTERS:
        return True
    return bool(letters & URDU_LIKELY_LETTERS) and not (letters & ARABIC_ONLY_LETTERS)


def title_language(title: str) -> str:
    """
    'en', 'ur' (Urdu script), 'roman_ur' (Roman Urdu) or 'other' (Arabic,
    Hindi/Devanagari, Roman Hindi, Telugu, …). Hashtags/emoji are ignored;
    mixed English + Urdu-script titles count as Urdu.
    """
    cleaned = _clean_text(title)
    non_latin = _non_latin_letters(cleaned)
    if non_latin > MAX_NON_LATIN_LETTERS:
        arabic = _arabic_script_letters(cleaned)
        # all the foreign letters are Arabic-script, and they are Urdu
        return "ur" if len(arabic) == non_latin and _is_urdu_script(cleaned) else "other"
    words = [w.lower() for w in re.findall(r"[A-Za-z]+", cleaned)]
    if not words:
        return "other"
    if set(words) & HINDI_MARKER_WORDS:
        return "other"
    share = english_word_share(cleaned)
    roman = [w for w in words if w in ROMAN_URDU_WORDS]
    if len(roman) >= ROMAN_URDU_MIN_WORDS:
        known = sum(1 for w in words if w in ROMAN_URDU_WORDS or (
            _zipf_frequency and _zipf_frequency(w, "en") >= ENGLISH_WORD_ZIPF))
        # English titles use 'the', 'is', 'do', 'in' too: only call it Roman
        # Urdu when the English-word share alone would not make it English
        if (known / len(words) >= MIN_KNOWN_WORD_SHARE or len(roman) / len(words) >= MIN_ROMAN_URDU_SHARE) \
                and (share is None or share < 0.8):
            return "roman_ur"
    if share is None or share >= MIN_ENGLISH_WORD_SHARE:
        return "en"
    return "other"


def _allowed_title_languages(languages: tuple[str, ...]) -> set[str]:
    allowed = {"en"} if "en" in languages else set()
    if "ur" in languages:
        allowed |= {"ur", "roman_ur"}
    return allowed


def _is_usable(video: dict, languages: tuple[str, ...] = ("en",)) -> bool:
    """
    Shorts only, real traction, known subscriber count, target language,
    real title. The channel name is script-checked too: romanised titles
    from non-Latin channels (e.g. Telugu) slip past the title check.
    languages: ("en",) by default; ("en", "ur") also keeps Urdu-script and
    Roman Urdu titles (never Arabic or Hindi).
    """
    lang = video.get("language", "").lower()
    basic = (0 < video["duration_s"] <= MAX_SHORT_SECONDS
             and video["views"] >= MIN_VIEWS
             and video.get("subscribers") is not None)
    if not basic:
        return False
    tag_ok = not lang or any(lang.startswith(x) for x in languages)
    if not tag_ok and not ("ur" in languages and lang.startswith(AMBIGUOUS_TAGS_FOR_URDU)
                           and title_language(video["title"]) in ("ur", "roman_ur")):
        return False
    if "ur" not in languages:
        return (_title_is_informative(video["title"])
                and not names_other_language(video)
                and _latin_ratio(video.get("channel", ""), if_no_letters=1.0) >= MIN_LATIN_RATIO)
    if len(_clean_text(video["title"]).split()) < MIN_TITLE_WORDS:
        return False
    if title_language(video["title"]) not in _allowed_title_languages(languages):
        return False
    if names_other_language(video, allowed={"urdu"}):
        return False
    channel = video.get("channel", "")
    return (_non_latin_letters(channel) <= MAX_NON_LATIN_LETTERS
            or (len(_arabic_script_letters(channel)) == _non_latin_letters(channel)
                and _is_urdu_script(channel)))


def collect_videos(queries: list[str], api_key: str, now: datetime,
                   languages: tuple[str, ...] = ("en",),
                   queries_ur: list[str] | None = None) -> list[dict]:
    """
    Run all searches, fetch details + subscriber counts, return usable Shorts.
    `queries` are searched with relevanceLanguage=en; with "ur" in
    `languages`, `queries_ur` (Urdu / Roman Urdu) are searched with
    relevanceLanguage=ur too, and Urdu titles are kept (see _is_usable).

    Raises:
        requests.HTTPError: if the very first search fails (bad key, quota).
    """
    all_ids: list[str] = []
    windows = (SEARCH_PUBLISHED_DAYS, RECENT_WINDOW_DAYS)
    searches = [(q, days, RELEVANCE_LANGUAGE) for q in queries for days in windows]
    if "ur" in languages:
        searches += [(q, days, "ur") for q in (queries_ur or []) for days in windows]
    for i, (query, days, search_lang) in enumerate(searches):
        if i > 0:
            time.sleep(0.2)
        try:
            ids = _search_video_ids(query, api_key, now, days, search_lang)
            print(f"[ResearchAgent] '{query}' ({days}d) → {len(ids)} videos")
            all_ids.extend(ids)
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            if not all_ids:
                raise
            print(f"[ResearchAgent] Search failed for '{query}' (HTTP {status}) — "
                  f"continuing with {len(all_ids)} videos")
            if status == 403:   # quota exceeded — further calls will fail too
                break

    unique_ids = list(dict.fromkeys(all_ids))
    if not unique_ids:
        return []

    videos = _fetch_video_details(unique_ids, api_key)
    channel_ids = list(dict.fromkeys(v["channel_id"] for v in videos if v["channel_id"]))
    channels = _fetch_channel_info(channel_ids, api_key)
    for v in videos:
        v["subscribers"] = channels.get(v["channel_id"], {}).get("subscribers")

    usable = [v for v in videos if _is_usable(v, languages)]
    for v in usable:
        v["title_language"] = title_language(v["title"]) if "ur" in languages else "en"
    print(f"[ResearchAgent] {len(unique_ids)} unique videos → {len(usable)} usable Shorts")

    if CHANNEL_BASELINE and usable:
        uploads = {v["channel_id"]: channels.get(v["channel_id"], {}).get("uploads", "")
                   for v in usable}
        baselines = _fetch_channel_baselines(uploads, api_key, now, set(unique_ids))
        for v in usable:
            v["channel_median_views"] = baselines.get(v["channel_id"])
        known = sum(b is not None for b in baselines.values())
        print(f"[ResearchAgent] Channel baselines: {known}/{len(baselines)} channels "
              f"(rest use the subscriber fallback)")
    return usable


# ─── [3] Scoring ───────────────────────────────────────────────────────────────

def _hours_since(published_at: str, now: datetime) -> float:
    try:
        published = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return 24.0
    return max((now - published).total_seconds() / 3600, 1.0)


def _minmax_log(values: list[float | None]) -> list[float | None]:
    """log1p then min-max to 0-1. None stays None. All-equal input → all zeros."""
    logged = [None if v is None else math.log1p(max(v, 0.0)) for v in values]
    known = [x for x in logged if x is not None]
    if not known:
        return logged
    lo, hi = min(known), max(known)
    if hi == lo:
        return [None if x is None else 0.0 for x in logged]
    return [None if x is None else (x - lo) / (hi - lo) for x in logged]


IG_BASELINE_FLOOR = 50   # likes+comments; stops tiny accounts getting huge outliers


def _raw_signals(v: dict) -> tuple[float | None, float, float | None]:
    """
    (outlier, velocity, engagement) for one post.
      youtube:   views / max(channel's median Shorts views, VIEW_BASELINE_FLOOR)
                 (fallback: views / max(subs, SUBSCRIBER_FLOOR)),
                 views/h, interactions / views
      instagram: interactions / creator's median interactions, interactions/h,
                 interactions / followers. Views of other people's Reels are
                 not in the API, so likes+comments stand in for them.
                 Hashtag posts have no known author → outlier/engagement None.
    """
    interactions = v["likes"] + v["comments"]
    hours = v["hours_since_upload"]
    if v.get("platform", "youtube") == "youtube":
        median = v.get("channel_median_views")
        if median is not None:
            v["baseline_source"] = "channel_median"
            outlier = v["views"] / max(median, VIEW_BASELINE_FLOOR)
        else:
            v["baseline_source"] = "subscribers"
            outlier = v["views"] / max(v.get("subscribers") or 0, SUBSCRIBER_FLOOR)
        return (outlier,
                v["views"] / hours,
                interactions / max(v["views"], 1))
    baseline = v.get("creator_baseline")
    followers = v.get("subscribers")
    return (interactions / max(baseline, IG_BASELINE_FLOOR) if baseline else None,
            interactions / hours,
            interactions / followers if followers else None)


def score_videos(videos: list[dict], now: datetime) -> list[dict]:
    """
    Add outlier, velocity, engagement and video_score to each post (in place).
    A signal that is unknown for a post (None) is left out of its score and
    the remaining weights are rescaled.
    """
    if not videos:
        return videos
    for v in videos:
        v["hours_since_upload"] = round(_hours_since(v["published_at"], now), 1)
        v["outlier"], v["velocity"], v["engagement"] = _raw_signals(v)

    norm_outlier = _minmax_log([v["outlier"] for v in videos])
    norm_velocity = _minmax_log([v["velocity"] for v in videos])
    norm_engagement = _minmax_log([None if v["engagement"] is None else v["engagement"] * 100
                                   for v in videos])
    for v, o, vel, eng in zip(videos, norm_outlier, norm_velocity, norm_engagement):
        parts = [(w, x) for w, x in ((W_OUTLIER, o), (W_VELOCITY, vel), (W_ENGAGEMENT, eng))
                 if x is not None]
        total_w = sum(w for w, _ in parts)
        v["video_score"] = round(sum(w * x for w, x in parts) / total_w, 4) if total_w else 0.0
    return videos


# ─── [4] Clustering ────────────────────────────────────────────────────────────


def video_text(video: dict) -> str:
    """
    Text used to embed a video: the cleaned title only. Tags and
    descriptions are mostly stuffed hashtags (#mindset #motivation) that
    make unrelated clip edits look on-topic, so they are left out.
    """
    return _clean_text(video["title"])


def collapse_near_duplicates(videos: list[dict], embeddings: np.ndarray
                             ) -> tuple[list[dict], np.ndarray]:
    """
    Content farms reupload the same Short across many channels, which would
    fake a "trend". Videos whose title embeddings have cosine ≥
    DUPLICATE_SIMILARITY count once: the best-scoring copy is kept and its
    duplicate_count records the rest.
    """
    order = sorted(range(len(videos)), key=lambda i: videos[i]["video_score"], reverse=True)
    kept: list[int] = []
    for i in order:
        match = next((k for k in kept
                      if float(embeddings[i] @ embeddings[k]) >= DUPLICATE_SIMILARITY), None)
        if match is None:
            videos[i]["duplicate_count"] = 0
            kept.append(i)
        else:
            videos[match]["duplicate_count"] += 1
    kept.sort()
    return [videos[i] for i in kept], embeddings[kept]


def cluster_embeddings(embeddings: np.ndarray, distance: float | None = None) -> list[list[int]]:
    """Agglomerative clustering on cosine distance → list of index groups."""
    n = len(embeddings)
    if n == 0:
        return []
    if n == 1:
        return [[0]]
    labels = AgglomerativeClustering(
        n_clusters=None,
        metric="cosine",
        linkage=CLUSTER_LINKAGE,
        distance_threshold=CLUSTER_DISTANCE_THRESHOLD if distance is None else distance,
    ).fit_predict(embeddings)
    groups: dict[int, list[int]] = {}
    for idx, label in enumerate(labels):
        groups.setdefault(int(label), []).append(idx)
    return list(groups.values())


# ─── [5] Trend Ranking ─────────────────────────────────────────────────────────

def _embed(texts: list[str], multilingual: bool = False) -> np.ndarray:
    """English model by default; the multilingual one for Urdu niches."""
    if multilingual:
        return embed_texts(texts, model_name=MULTILINGUAL_EMBEDDING_MODEL)
    return embed_texts(texts)


def _profile_embedding(profile: dict, niche: str, multilingual: bool = False) -> np.ndarray | None:
    """One embedding per recurring topic (fallback: niche)."""
    topics = [t for t in profile.get("recurring_topics", []) if t] or ([niche] if niche else [])
    if not topics:
        return None
    return _embed(topics, multilingual)


def growth_stats(members: list[dict]) -> dict:
    """
    Upload rate in the last RECENT_WINDOW_DAYS vs the rest of the search
    window, per day, smoothed:
      growth_ratio = (recent/3 + 0.5) / (earlier/11 + 0.5)
    > 1 means the topic is getting more uploads now than before.
    """
    recent_hours = RECENT_WINDOW_DAYS * 24
    earlier_days = max(SEARCH_PUBLISHED_DAYS - RECENT_WINDOW_DAYS, 1)
    recent = sum(1 for v in members if v["hours_since_upload"] <= recent_hours)
    earlier = len(members) - recent
    ratio = ((recent / RECENT_WINDOW_DAYS + GROWTH_SMOOTHING)
             / (earlier / earlier_days + GROWTH_SMOOTHING))
    return {"recent_count": recent, "earlier_count": earlier, "growth_ratio": round(ratio, 3)}


def recent_share(members: list[dict]) -> float:
    """Share of posts uploaded in the last RECENT_WINDOW_DAYS (clamped to 5–95 %)."""
    if not members:
        return 0.5
    g = growth_stats(members)
    return min(max(g["recent_count"] / len(members), 0.05), 0.95)


def relative_growth(recent: int, earlier: int, niche_share: float) -> float:
    """
    How much faster a cluster grows than the niche as a whole:
        (cluster recent/earlier odds) ÷ (niche recent/earlier odds)
    which equals (cluster rate ratio) ÷ (niche rate ratio), because both
    windows have the same lengths. GROWTH_PRIOR_POSTS pseudo-posts at the
    niche's own share pull small clusters toward 1.0 (= "like the niche"),
    not toward 0 or ∞, so 3 posts can't fake a spike and the sampling bias
    of the search (same for every cluster) cancels out.
    """
    m, p = GROWTH_PRIOR_POSTS, niche_share
    cluster_odds = (recent + p * m) / (earlier + (1 - p) * m)
    return cluster_odds / (p / (1 - p))


def classify_trend(checks: dict[str, bool], creators: int, growth_measured: bool = True,
                   require_measured: bool | None = None) -> str:
    """
    Trend definition → trend_type (see module docstring, step [5]).
    With require_measured (default REQUIRE_MEASURED_GROWTH), a cluster whose
    growth is only estimated (no earlier snapshot yet) can be at most
    "emerging", never "trend".
    """
    if require_measured is None:
        require_measured = REQUIRE_MEASURED_GROWTH
    if creators < MIN_CLUSTER_CHANNELS:
        return "one_off_viral" if checks["overperforms"] else "single_creator"
    if all(checks.values()):
        return "trend" if growth_measured or not require_measured else "emerging"
    if checks["overperforms"] and checks["growing"] and creators < MIN_TREND_CHANNELS:
        return "emerging"
    if checks["spreading"] and not checks["growing"]:
        return "evergreen"
    return "topic"


def _growth_score(ratio: float) -> float:
    """growth_ratio → 0-1: ≤ 1 (not growing) is 0, ≥ GROWTH_SCORE_CAP is 1."""
    if ratio <= 1.0:
        return 0.0
    return min(math.log(ratio) / math.log(GROWTH_SCORE_CAP), 1.0)


def _majority_platform(members: list[dict]) -> str:
    platforms = [v.get("platform", "youtube") for v in members]
    return max(set(platforms), key=platforms.count)


def build_trends(videos: list[dict], embeddings: np.ndarray, clusters: list[list[int]],
                 topic_embeddings: np.ndarray | None,
                 niche_share: float | None = None,
                 niche_acceleration: float | None = None,
                 require_measured: bool | None = None,
                 min_fit: float | None = None) -> list[dict]:
    """
    Turn clusters into ranked trend dicts using the trend definition.
    Clusters with creator_fit < MIN_CREATOR_FIT are dropped first (when the
    creator has topics): viral content outside the niche is not a trend for them.
    Every remaining cluster with ≥ MIN_WEAK_CLUSTER_SIZE posts gets the four
    checks and a trend_type; one-creator clusters are hidden. Ranking is by
    trend_type first, then trend_score. Only "trend" is high confidence.
    Posts with no known author (Instagram hashtag posts) count for volume,
    but not for creators, over-performance or growth.

    niche_share: recent_share() of ALL posts in the run. When given, "growing"
    means growing faster than the niche as a whole (see relative_growth()).
    This cancels sampling bias that hits every cluster equally — e.g.
    YouTube's extra 3-day search over-samples recent uploads, which would
    otherwise make every topic look like it is growing.

    niche_acceleration: median view acceleration (trend_snapshots.py) of all
    posts measured in this run. When a cluster has ≥ MIN_MEASURED_MEMBERS
    measured posts, "growing" uses measured_growth = cluster median
    acceleration ÷ niche_acceleration instead of the upload-rate estimate
    (growth_source "snapshot" vs "estimate").
    Summary numbers are medians so one viral post can't skew a cluster.
    """
    def channel_count(group: list[int]) -> int:
        return len({videos[i]["channel_id"] for i in group if videos[i].get("channel_id")})

    has_topics = topic_embeddings is not None and len(topic_embeddings) > 0

    def centroid_fit(group: list[int]) -> float:
        if not has_topics:
            return 0.0
        centroid = embeddings[group].mean(axis=0)
        centroid = centroid / (np.linalg.norm(centroid) or 1.0)
        return float(max(0.0, (topic_embeddings @ centroid).max()))

    fit = {tuple(g): centroid_fit(g) for g in clusters}
    min_fit = MIN_CREATOR_FIT if min_fit is None else min_fit
    if has_topics:
        relevant = [g for g in clusters if fit[tuple(g)] >= min_fit]
        print(f"[ResearchAgent] Creator-fit gate (≥ {min_fit}): "
              f"{len(clusters)} → {len(relevant)} clusters")
        clusters = relevant

    def median_of(members: list[dict], key: str) -> float | None:
        known = [v[key] for v in members if v.get(key) is not None]
        return statistics.median(known) if known else None

    candidates = [g for g in clusters if len(g) >= MIN_WEAK_CLUSTER_SIZE]
    max_channels = max((channel_count(g) for g in candidates), default=1) or 1
    trends, hidden = [], {}
    for group in candidates:
        members = sorted((videos[i] for i in group), key=lambda v: v["video_score"], reverse=True)
        creators = channel_count(group)
        median_outlier = median_of(members, "outlier")
        # Hashtag recent_media only covers 24 h, so unattributed posts would
        # inflate the recent window; growth uses attributed posts only.
        growth = growth_stats([v for v in members if v.get("channel_id")])
        growth["relative_growth"] = growth["growth_ratio"] if niche_share is None else round(
            relative_growth(growth["recent_count"], growth["earlier_count"], niche_share), 3)
        measured = [v["acceleration"] for v in members if v.get("acceleration") is not None]
        if niche_acceleration and len(measured) >= MIN_MEASURED_MEMBERS:
            growth["measured_growth"] = round(statistics.median(measured) / niche_acceleration, 3)
            growth["growth_source"] = "snapshot"
        else:
            growth["measured_growth"] = None
            growth["growth_source"] = "estimate"
        growth["measured_posts"] = len(measured)
        growth_value = (growth["measured_growth"] if growth["growth_source"] == "snapshot"
                        else growth["relative_growth"])
        checks = {
            "overperforms": median_outlier is not None and median_outlier >= OVERPERFORM_OUTLIER,
            "growing": growth_value >= GROWTH_RATIO_MIN,
            "spreading": creators >= MIN_TREND_CHANNELS,
            "recent": statistics.median(v["hours_since_upload"] for v in members)
                      <= SEARCH_PUBLISHED_DAYS * 24,
        }
        trend_type = classify_trend(checks, creators, growth["growth_source"] == "snapshot",
                                    require_measured)
        if trend_type in HIDDEN_TYPES:
            hidden[trend_type] = hidden.get(trend_type, 0) + 1
            continue

        creator_fit = fit[tuple(group)]
        strength = statistics.median(v["video_score"] for v in members)
        trend_score = (W_STRENGTH * strength + W_GROWTH * _growth_score(growth_value)
                       + W_SPREAD * creators / max_channels + W_FIT * creator_fit)
        median_engagement = median_of(members, "engagement")

        trends.append({
            "trend_type": trend_type,
            "checks": checks,
            "trend_score": round(trend_score, 4),
            "creator_fit": round(creator_fit, 4),
            "platform": _majority_platform(members),
            "median_velocity": round(statistics.median(v["velocity"] for v in members), 1),
            "median_outlier": None if median_outlier is None else round(median_outlier, 3),
            "median_engagement": None if median_engagement is None else round(median_engagement, 4),
            **growth,
            "video_count": len(members),
            "channel_count": creators,
            "unattributed_count": sum(1 for v in members if not v.get("channel_id")),
            "low_confidence": trend_type != "trend",
            "titles": [v["title"] for v in members[:TITLES_FOR_LABELING]],
            "evidence": [{
                "video_id": v["video_id"],
                "url": v.get("url") or f"https://www.youtube.com/shorts/{v['video_id']}",
                "title": v["title"],
                "channel": v["channel"],
                "views": v.get("views"),
                "likes": v["likes"],
                "comments": v["comments"],
                "subscribers": v.get("subscribers"),
                "channel_median_views": v.get("channel_median_views"),
                "outlier": None if v["outlier"] is None else round(v["outlier"], 3),
                "acceleration": None if v.get("acceleration") is None else round(v["acceleration"], 3),
                "velocity": round(v["velocity"], 1),
                "published_at": v.get("published_at", ""),
                "published_hours_ago": v["hours_since_upload"],
                "reuploads": v.get("duplicate_count", 0),
                "found_via": v.get("found_via", "search"),
            } for v in members[:EVIDENCE_PER_TREND]],
        })

    if hidden:
        print(f"[ResearchAgent] Hidden single-creator clusters: {hidden}")
    counts = {t: sum(1 for x in trends if x["trend_type"] == t) for t in TYPE_RANK}
    print(f"[ResearchAgent] Trend types: {counts}")
    trends.sort(key=lambda t: (TYPE_RANK[t["trend_type"]], -t["trend_score"]))
    return trends


# ─── [6] Labeling ──────────────────────────────────────────────────────────────

def _format_count(n: float) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return f"{n:.0f}"


def _fallback_label(trend: dict) -> dict:
    """Non-LLM label: cleaned best title + a factual summary."""
    name = next((_clean_text(t) for t in trend["titles"] if len(_clean_text(t)) >= 5),
                trend["titles"][0] if trend["titles"] else "Untitled trend")
    return {"topic": name[:80], "suggested_angle": ""}


PLATFORM_WORDS = {
    # platform: (post noun, creator noun, velocity unit, outlier meaning)
    "youtube": ("Shorts", "channels", "views/hour",
                "its channel's normal (median Shorts views, or subscribers if unknown)"),
    "instagram": ("Reels", "creators", "likes+comments/hour",
                  "its creator's usual likes+comments"),
}


def _why_trending(trend: dict) -> str:
    """Factual summary built only from measured numbers."""
    posts, creators, unit, outlier_meaning = PLATFORM_WORDS[trend.get("platform", "youtube")]
    extra = (f" (+{trend['unattributed_count']} hashtag posts)"
             if trend.get("unattributed_count") else "")
    text = (f"{trend['video_count'] - trend.get('unattributed_count', 0)} {posts} from "
            f"{trend['channel_count']} {creators}{extra} in the last {SEARCH_PUBLISHED_DAYS} days; "
            f"the typical one gets {_format_count(trend['median_velocity'])} {unit}")
    if trend.get("median_outlier") is not None:
        text += f" and {trend['median_outlier']:.1f}× {outlier_meaning}"
    text += "."
    if trend.get("growth_source") == "snapshot":
        text += (f" Measured since the last snapshot, its views are speeding up "
                 f"{trend['measured_growth']:.1f}× as fast as the niche overall.")
    elif "relative_growth" in trend:
        text += (f" Its upload rate in the last {RECENT_WINDOW_DAYS} days is growing "
                 f"{trend['relative_growth']:.1f}× as fast as the niche overall (estimate).")
    return text


def _first_sentence(text: str, max_chars: int = 200) -> str:
    """Small models ignore 'one sentence' — keep only the first one."""
    text = " ".join(str(text).split())
    first = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0]
    return first[:max_chars].rstrip()


def label_trend(trend: dict, niche: str) -> dict:
    """
    Ask the local LLM to name the cluster and suggest an angle.

    Raises:
        LocalLLMError: caller switches to _fallback_label for this run.
    """
    titles = "\n".join(f"- {t}" for t in trend["titles"])
    platform = ("Instagram Reels" if trend.get("platform") == "instagram"
                else "YouTube Shorts")
    prompt = (
        f"These {platform} are all trending around one topic:\n"
        f"{titles}\n\n"
        f"Creator niche: {niche}\n\n"
        "1. topic: name the shared topic in 3-8 words (a clear topic, not a clickbait title).\n"
        "2. why_trending: one sentence on why viewers are drawn to it.\n"
        "3. suggested_angle: one sentence on how this creator could cover it.\n"
        "Do not include any numbers or statistics.\n"
        'Return JSON: {"topic": "...", "why_trending": "...", "suggested_angle": "..."}'
    )
    result = chat_json(prompt, temperature=0.3, max_tokens=250)
    topic = str(result.get("topic", "")).strip()
    if not 3 <= len(topic) <= 100:
        raise LocalLLMError(f"Unusable topic label: {topic!r}")
    return {
        "topic": topic,
        "why_trending": _first_sentence(result.get("why_trending", "")),
        "suggested_angle": _first_sentence(result.get("suggested_angle", "")),
    }


def label_trends(trends: list[dict], niche: str) -> None:
    """Label trends in place. Stops calling the LLM after the first failure."""
    llm_available = True
    for trend in trends:
        label = None
        if llm_available:
            try:
                label = label_trend(trend, niche)
            except LocalLLMError as e:
                print(f"[ResearchAgent] Label LLM unavailable — using title fallback ({e})")
                llm_available = False
        if label is None:
            label = _fallback_label(trend)
        trend["topic"] = label["topic"]
        trend["suggested_angle"] = label.get("suggested_angle", "")
        trend["why_trending"] = label.get("why_trending") or ""
        trend["data_summary"] = _why_trending(trend)
        trend["labeled_by"] = "local_llm" if llm_available else "title_fallback"
        trend.pop("titles", None)


# ─── Orchestration ─────────────────────────────────────────────────────────────

SOURCE_NAMES = {"youtube": "youtube_data_api", "instagram": "instagram_graph_api"}


def _apply_snapshots(videos: list[dict], niche: str, now: datetime, api_key: str,
                     stats: dict) -> None:
    """
    Measure growth from earlier snapshots, then store today's: sets
    v["acceleration"] (None without history), re-reads the views of videos
    tracked in the last HISTORY_DAYS that today's search did not return
    (1 unit per 50, so each video's series continues), and writes the
    snapshot. stats gets snapshot_days, posts_measured, niche_acceleration.
    """
    key = snapshots.niche_key(niche)
    history = snapshots.load_history(SNAPSHOT_DIR, key, now)
    for v in videos:
        v["acceleration"] = snapshots.acceleration(v["video_id"], v["views"],
                                                   v.get("published_at", ""), now, history)
    seen = {v["video_id"] for v in videos}
    latest: dict[str, dict] = {}
    for snap in reversed(history):          # oldest first, so newer entries win
        latest.update(snap)
    tracked = [vid for vid in latest if vid not in seen]
    extra = []
    if tracked:
        try:
            counts = _fetch_view_counts(tracked, api_key)
            extra = [{"video_id": vid, "views": views, "published_at": latest[vid]["published_at"],
                      "channel_id": latest[vid]["channel_id"]} for vid, views in counts.items()]
        except requests.RequestException as e:
            print(f"[ResearchAgent] Could not refresh tracked videos: {e}")
    snapshots.save_snapshot(SNAPSHOT_DIR, key, now, videos + extra)

    measured = [v["acceleration"] for v in videos if v["acceleration"] is not None]
    stats["snapshot_days"] = len(history)    # snapshot files of the last HISTORY_DAYS
    stats["posts_measured"] = len(measured)
    stats["tracked_refreshed"] = len(extra)
    stats["niche_acceleration"] = round(statistics.median(measured), 3) if measured else None
    print(f"[ResearchAgent] Snapshots: {stats['snapshot_days']} file(s) in history, "
          f"{len(measured)}/{len(videos)} posts measured, {len(extra)} tracked videos refreshed")


def _collect_youtube(queries: list[str], now: datetime, api_key: str | None,
                     stats: dict, niche: str = "", languages: tuple[str, ...] = ("en",),
                     queries_ur: list[str] | None = None) -> tuple[list[dict] | None, str | None]:
    api_key = api_key if api_key is not None else os.getenv("YOUTUBE_API_KEY", "")
    if not api_key:
        return None, "YOUTUBE_API_KEY not set"
    YOUTUBE_QUOTA_USED["units"] = 0
    try:
        if "ur" in languages:
            videos = collect_videos(queries, api_key, now, languages=languages, queries_ur=queries_ur)
        else:
            videos = collect_videos(queries, api_key, now)
        if SNAPSHOTS and videos:
            _apply_snapshots(videos, niche, now, api_key, stats)
    except requests.RequestException as e:
        status = getattr(getattr(e, "response", None), "status_code", 0)
        return None, f"YouTube API error (HTTP {status}): {e}"
    finally:
        stats["api_cost"] = f"{YOUTUBE_QUOTA_USED['units']} YouTube quota units"
    return videos, None


def _collect_instagram(queries: list[str], niche: str, now: datetime, ig_config: dict | None,
                       stats: dict) -> tuple[list[dict] | None, str | None]:
    from pipeline.agents import instagram_source as ig   # lazy: only V2 needs it
    config = ig_config if ig_config is not None else ig.config_from_env()
    missing = ig.missing_config(config)
    if missing:
        return None, f"Instagram source not configured: {', '.join(missing)}"
    try:
        posts, ig_stats = ig.collect_posts(queries, config, now)
    except ig.InstagramAPIError as e:
        return None, f"Instagram API error: {e}"
    stats.update(ig_stats)
    return posts, None


def run_research(profile: dict, niche: str, top_k: int = TOP_K_TRENDS,
                 now: datetime | None = None,
                 api_key: str | None = None,
                 source: str | None = None,
                 ig_config: dict | None = None,
                 queries: list[str] | None = None,
                 languages: list[str] | tuple[str, ...] | None = None,
                 queries_ur: list[str] | None = None) -> dict:
    """
    Full research run. languages: ("en",) (default, or TREND_LANGUAGES) or
    ("en", "ur") to also keep Urdu-script and Roman Urdu Shorts (YouTube
    only); Urdu runs also search `queries_ur` and embed with the
    multilingual model. source = "youtube" (V1) or "instagram" (V2); default
    from TREND_SOURCE, else youtube. Returns:
      { "trends": [...], "queries": [...], "source": str, "error": str | None,
        "stats": {posts, clusters, trend_types, api_cost, ...} }

    Never raises: failures produce an empty trend list and an error message.
    """
    now = now or datetime.now(timezone.utc)
    source = (source or os.getenv("TREND_SOURCE", "") or "youtube").strip().lower()
    stats: dict[str, Any] = {"version": source}
    languages = tuple(languages or DEFAULT_LANGUAGES)
    multilingual = "ur" in languages and source == "youtube"
    min_fit = MULTILINGUAL_MIN_CREATOR_FIT if multilingual else MIN_CREATOR_FIT
    stats["languages"] = list(languages)

    queries = queries or generate_queries(profile, niche)   # fixed queries: experiments
    print(f"[ResearchAgent] Source: {source} | Queries: {queries}")

    def fail(error: str, reached_api: bool = False) -> dict:
        return {"trends": [], "queries": queries, "error": error, "stats": stats,
                "source": SOURCE_NAMES.get(source, "none") if reached_api else "none"}

    if source == "youtube":
        videos, error = _collect_youtube(queries, now, api_key, stats, niche, languages, queries_ur)
    elif source == "instagram":
        videos, error = _collect_instagram(queries, niche, now, ig_config, stats)
    else:
        return fail(f"Unknown TREND_SOURCE {source!r} (use youtube or instagram)")
    if error:
        return fail(error)

    stats["posts_usable"] = len(videos)
    if not videos:
        return fail("No usable posts found for these queries", reached_api=True)

    score_videos(videos, now)
    if multilingual:
        stats["posts_by_language"] = {k: sum(1 for v in videos if v.get("title_language") == k)
                                      for k in ("en", "ur", "roman_ur")}
    embeddings = _embed([video_text(v) for v in videos], multilingual)
    before = len(videos)
    videos, embeddings = collapse_near_duplicates(videos, embeddings)
    stats["posts_distinct"] = len(videos)
    print(f"[ResearchAgent] Near-duplicates collapsed: {before} → {len(videos)} distinct posts")
    clusters = cluster_embeddings(embeddings, MULTILINGUAL_CLUSTER_DISTANCE if multilingual else None)
    stats["clusters"] = len(clusters)
    print(f"[ResearchAgent] {len(clusters)} clusters, sizes: "
          f"{sorted((len(c) for c in clusters), reverse=True)[:10]}")

    niche_share = recent_share([v for v in videos if v.get("channel_id")])
    stats["niche_recent_share"] = round(niche_share, 3)
    all_trends = build_trends(videos, embeddings, clusters,
                              _profile_embedding(profile, niche, multilingual),
                              niche_share=niche_share,
                              niche_acceleration=stats.get("niche_acceleration"),
                              # only YouTube keeps snapshots; V2 has no measured growth
                              require_measured=REQUIRE_MEASURED_GROWTH and source == "youtube"
                              and SNAPSHOTS,
                              min_fit=min_fit)
    stats["trend_types"] = {t: sum(1 for x in all_trends if x["trend_type"] == t)
                            for t in TYPE_RANK}
    trends = all_trends[:top_k]
    if not trends:
        return fail(f"No multi-creator cluster matched the creator's topics "
                    f"(creator_fit < {min_fit})", reached_api=True)
    label_trends(trends, niche)
    return {"trends": trends, "queries": queries, "source": SOURCE_NAMES[source],
            "error": None, "stats": stats}


def _to_research_output(result: dict, profile: dict, niche: str) -> dict:
    """
    Shape run_research() output for pipeline state. The top trend fills the
    legacy single-topic fields the Scripting Agent reads; all trends are
    kept under "trends".
    """
    trends = result["trends"]
    if not trends:
        topics = profile.get("recurring_topics") or [niche or "general"]
        return {
            "topic": topics[0],
            "trend_score": 0.0,
            "trend_signals": {"velocity": 0.0, "engagement_rate": 0.0, "outlier": 0.0},
            "niche": niche,
            "supporting_evidence": [],
            "related_keywords": result["queries"],
            "cluster_size": 0,
            "low_confidence": True,
            "source": "profile_fallback",
            "trends": [],
        }

    best = trends[0]
    return {
        "topic": best["topic"],
        "trend_score": best["trend_score"],
        "trend_signals": {
            "velocity": best["median_velocity"],
            "engagement_rate": best["median_engagement"] or 0.0,
            "outlier": best["median_outlier"] or 0.0,
            "growth_ratio": best["growth_ratio"],
        },
        "trend_type": best["trend_type"],
        "trend_checks": best["checks"],
        "creator_fit": best["creator_fit"],
        "why_trending": best["why_trending"] or best["data_summary"],
        "suggested_angle": best["suggested_angle"],
        "niche": niche,
        "supporting_evidence": [
            {"video_title": e["title"], "channel": e["channel"], "views": e["views"],
             "published_hours_ago": e["published_hours_ago"], "url": e["url"]}
            for e in best["evidence"]
        ],
        "related_keywords": result["queries"],
        "cluster_size": best["video_count"],
        "low_confidence": best["low_confidence"],
        "source": result["source"],
        "trends": trends,
    }


# ─── LangGraph Node ────────────────────────────────────────────────────────────

def research_agent(state: PipelineState, run: Callable[..., dict] = run_research) -> dict[str, Any]:
    """
    LangGraph node: Research Agent.

    Reads creator_niche + creator_profile, finds trending topics from real
    YouTube Shorts, and writes research_output (top trend + all trends).
    """
    niche = state.get("creator_niche", "")
    profile = state.get("creator_profile") or {}
    print(f"\n[ResearchAgent] creator_id={state.get('creator_id', 'unknown')}, niche='{niche}'")

    try:
        result = run(profile, niche)
    except Exception as e:  # last line of defence — the graph must not crash
        result = {"trends": [], "queries": _fallback_queries(profile, niche),
                  "source": "none", "error": f"ResearchAgent failed: {e}"}

    output = _to_research_output(result, profile, niche)
    print(f"[ResearchAgent] Selected topic: '{output['topic'][:70]}' (source={output['source']})")
    return {"research_output": output, "research_error": result["error"]}
