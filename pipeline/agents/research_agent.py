"""
research_agent.py — LangGraph Research Agent Node (YouTube Data API v3)
========================================================================
Finds what is trending in the creator's niche RIGHT NOW, using real
YouTube Shorts data. Every number in the output comes from real videos;
the local LLM only does language work (queries, names, explanations).

Flow:
  [1] Query generation   local LLM turns the creator profile into 5 short
                         search-bar queries (fallback: recurring_topics + niche).
  [2] Discovery          search.list (last 14 days, short, English, by views)
                         → videos.list (stats + duration, keep ≤ 180 s)
                         → channels.list (subscriber counts).
                         Drops hashtag-only titles and non-Latin-script
                         titles or channel names.
  [3] Scoring            outlier    = views / max(subs, 1000)
                         velocity   = views / hours_since_upload
                         engagement = (likes + comments) / views
                         log-scale → min-max → weighted video_score.
  [4] Clustering         all-MiniLM-L6-v2 embeddings of the cleaned title
                         (tags are hashtag spam) → near-duplicates collapsed
                         → AgglomerativeClustering (cosine, complete).
                         Clusters with ≥ 3 videos from ≥ 2 channels rank
                         first; 2-video clusters fill the rest (low confidence).
  [5] Trend ranking      Clusters with creator_fit < 0.45 are dropped.
                         0.5 strength (median video_score) + 0.2 channel spread
                         + 0.3 creator_fit (cosine vs recurring_topics).
                         Median outlier < 1.5× → low confidence (not
                         over-performing, just a topic).
  [6] Labeling           local LLM names each top cluster and explains it.
                         Never outputs numbers. Fallback: cleaned top title.

Fallback:
  If YOUTUBE_API_KEY is missing or the API fails, the node returns the
  creator's first recurring topic with trend_score 0 and low_confidence,
  plus research_error. Scores are never invented. The graph never crashes.

Quota cost per full run:
  search.list   = 100 units × 5 queries = 500 units
  videos.list   = 1 unit per 50 IDs     ≈ 5 units
  channels.list = 1 unit per 50 IDs     ≈ 5 units
  Total         ≈ 510 units / run  (free quota 10,000/day → ~19 runs/day)
  Search results are cached in pipeline/cache/ for 6 hours.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import statistics
import sys
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

# ─── Configuration ─────────────────────────────────────────────────────────────
CACHE_DIR = Path(__file__).parent.parent / "cache"
CACHE_TTL_HOURS = 6

MAX_QUERIES = 5
SEARCH_MAX_RESULTS = 50          # per query (API maximum)
SEARCH_PUBLISHED_DAYS = 14       # only videos uploaded in the last N days
RELEVANCE_LANGUAGE = "en"
MAX_SHORT_SECONDS = 180          # YouTube Shorts can be up to 3 minutes
MIN_VIEWS = 1000                 # ignore videos with no real traction yet
SUBSCRIBER_FLOOR = 1000          # stops 10-sub channels getting huge outlier scores

MIN_TITLE_WORDS = 3              # after hashtags/emoji are stripped
MIN_LATIN_RATIO = 0.7            # drops Devanagari/Urdu titles with no language tag

# Video score weights (step 3)
W_OUTLIER, W_VELOCITY, W_ENGAGEMENT = 0.45, 0.35, 0.20

# Clustering (step 4)
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
CLUSTER_LINKAGE = "complete"      # every pair in a cluster must be similar
CLUSTER_DISTANCE_THRESHOLD = 0.6  # cosine distance; lower = tighter clusters
DUPLICATE_SIMILARITY = 0.95       # cosine ≥ this = same video reuploaded
MIN_CLUSTER_SIZE = 3
MIN_WEAK_CLUSTER_SIZE = 2         # used only to fill remaining slots
MIN_CLUSTER_CHANNELS = 2
OVERPERFORM_OUTLIER = 1.5         # median views ÷ subs below this = not over-performing
MIN_CREATOR_FIT = 0.45            # cosine vs recurring_topics; below = outside the niche

# Trend score weights (step 5) — strength leads so fit can't lift a dead topic
W_STRENGTH, W_SPREAD, W_FIT = 0.50, 0.20, 0.30

TOP_K_TRENDS = 5
EVIDENCE_PER_TREND = 5
TITLES_FOR_LABELING = 8

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"


# ─── Cache Utilities ───────────────────────────────────────────────────────────

def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{hashlib.md5(key.encode()).hexdigest()}.json"


def _load_cache(key: str) -> Any | None:
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            cached = json.load(f)
        cached_at = datetime.fromisoformat(cached.get("cached_at", "2000-01-01"))
        if datetime.now() - cached_at > timedelta(hours=CACHE_TTL_HOURS):
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

def _published_after_iso(now: datetime) -> str:
    cutoff = now - timedelta(days=SEARCH_PUBLISHED_DAYS)
    return cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")


def _search_video_ids(query: str, api_key: str, now: datetime) -> list[str]:
    """search.list — 100 quota units per call. Cached for CACHE_TTL_HOURS."""
    cache_key = f"search_v3_{query}_{now.strftime('%Y-%m-%d')}"
    cached = _load_cache(cache_key)
    if cached is not None:
        print(f"  [cache] search results for '{query}'")
        return cached

    response = requests.get(YOUTUBE_SEARCH_URL, params={
        "part": "id",
        "q": query,
        "type": "video",
        "videoDuration": "short",          # < 4 min; exact ≤ 180 s filter below
        "publishedAfter": _published_after_iso(now),
        "relevanceLanguage": RELEVANCE_LANGUAGE,
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
        })
    return videos


def _fetch_subscribers(channel_ids: list[str], api_key: str) -> dict[str, int | None]:
    """channel_id → subscriber count (None when the channel hides it)."""
    subs: dict[str, int | None] = {}
    for item in _batched_get(YOUTUBE_CHANNELS_URL, channel_ids, "statistics", api_key):
        stats = item.get("statistics", {})
        hidden = stats.get("hiddenSubscriberCount", False)
        subs[item["id"]] = None if hidden else int(stats.get("subscriberCount", 0))
    return subs


def _latin_ratio(text: str, if_no_letters: float = 0.0) -> float:
    """Share of letters that are ASCII (Latin script)."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return if_no_letters
    return sum(c.isascii() for c in letters) / len(letters)


def _title_is_informative(title: str) -> bool:
    """
    Hashtag-only titles ('#motivation #shorts') carry no topic signal and
    all look alike once cleaned; non-Latin titles slip past missing
    language tags. Both are dropped.
    """
    cleaned = _clean_text(title)
    return len(cleaned.split()) >= MIN_TITLE_WORDS and _latin_ratio(cleaned) >= MIN_LATIN_RATIO


def _is_usable(video: dict) -> bool:
    """
    Shorts only, real traction, known subscriber count, target language,
    real title. The channel name is script-checked too: romanised titles
    from non-Latin channels (e.g. Telugu) slip past the title check.
    """
    lang = video.get("language", "").lower()
    return (
        0 < video["duration_s"] <= MAX_SHORT_SECONDS
        and video["views"] >= MIN_VIEWS
        and video.get("subscribers") is not None
        and (not lang or lang.startswith(RELEVANCE_LANGUAGE))
        and _title_is_informative(video["title"])
        and _latin_ratio(video.get("channel", ""), if_no_letters=1.0) >= MIN_LATIN_RATIO
    )


def collect_videos(queries: list[str], api_key: str, now: datetime) -> list[dict]:
    """
    Run all searches, fetch details + subscriber counts, return usable Shorts.

    Raises:
        requests.HTTPError: if the very first search fails (bad key, quota).
    """
    all_ids: list[str] = []
    for i, query in enumerate(queries):
        if i > 0:
            time.sleep(0.2)
        try:
            ids = _search_video_ids(query, api_key, now)
            print(f"[ResearchAgent] '{query}' → {len(ids)} videos")
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
    subscribers = _fetch_subscribers(channel_ids, api_key)
    for v in videos:
        v["subscribers"] = subscribers.get(v["channel_id"])

    usable = [v for v in videos if _is_usable(v)]
    print(f"[ResearchAgent] {len(unique_ids)} unique videos → {len(usable)} usable Shorts")
    return usable


# ─── [3] Scoring ───────────────────────────────────────────────────────────────

def _hours_since(published_at: str, now: datetime) -> float:
    try:
        published = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return 24.0
    return max((now - published).total_seconds() / 3600, 1.0)


def _minmax_log(values: list[float]) -> list[float]:
    """log1p then min-max to 0-1. All-equal input → all zeros."""
    logged = [math.log1p(max(v, 0.0)) for v in values]
    lo, hi = min(logged), max(logged)
    if hi == lo:
        return [0.0] * len(logged)
    return [(x - lo) / (hi - lo) for x in logged]


def score_videos(videos: list[dict], now: datetime) -> list[dict]:
    """Add outlier, velocity, engagement and video_score to each video (in place)."""
    if not videos:
        return videos
    for v in videos:
        views = max(v["views"], 1)
        v["hours_since_upload"] = round(_hours_since(v["published_at"], now), 1)
        v["outlier"] = v["views"] / max(v.get("subscribers") or 0, SUBSCRIBER_FLOOR)
        v["velocity"] = v["views"] / v["hours_since_upload"]
        v["engagement"] = (v["likes"] + v["comments"]) / views

    norm_outlier = _minmax_log([v["outlier"] for v in videos])
    norm_velocity = _minmax_log([v["velocity"] for v in videos])
    norm_engagement = _minmax_log([v["engagement"] * 100 for v in videos])
    for v, o, vel, eng in zip(videos, norm_outlier, norm_velocity, norm_engagement):
        v["video_score"] = round(W_OUTLIER * o + W_VELOCITY * vel + W_ENGAGEMENT * eng, 4)
    return videos


# ─── [4] Clustering ────────────────────────────────────────────────────────────

_embedder = None


def embed_texts(texts: list[str]) -> np.ndarray:
    """all-MiniLM-L6-v2 → (n, 384) L2-normalised matrix. Model loads once (CPU)."""
    global _embedder
    if _embedder is None:
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer(EMBEDDING_MODEL, device="cpu")
    return np.asarray(_embedder.encode(texts, normalize_embeddings=True, show_progress_bar=False))


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


def cluster_embeddings(embeddings: np.ndarray) -> list[list[int]]:
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
        distance_threshold=CLUSTER_DISTANCE_THRESHOLD,
    ).fit_predict(embeddings)
    groups: dict[int, list[int]] = {}
    for idx, label in enumerate(labels):
        groups.setdefault(int(label), []).append(idx)
    return list(groups.values())


# ─── [5] Trend Ranking ─────────────────────────────────────────────────────────

def _profile_embedding(profile: dict, niche: str) -> np.ndarray | None:
    """One embedding per recurring topic (fallback: niche)."""
    topics = [t for t in profile.get("recurring_topics", []) if t] or ([niche] if niche else [])
    if not topics:
        return None
    return embed_texts(topics)


def build_trends(videos: list[dict], embeddings: np.ndarray, clusters: list[list[int]],
                 topic_embeddings: np.ndarray | None) -> list[dict]:
    """
    Turn clusters into ranked trend dicts.
    Clusters with creator_fit < MIN_CREATOR_FIT are dropped first (when the
    creator has topics): viral content outside the niche is not a trend for them.
      strong: ≥ MIN_CLUSTER_SIZE videos from ≥ MIN_CLUSTER_CHANNELS channels
      weak:   ≥ MIN_WEAK_CLUSTER_SIZE videos from ≥ MIN_CLUSTER_CHANNELS channels
    Strong trends always rank above weak ones; weak ones are low_confidence.
    A strong cluster whose median outlier is below OVERPERFORM_OUTLIER is
    also low_confidence: its videos only got the views their channel size
    predicts, so it is a topic, not a trend.
    If neither exists, any clusters are used (all low_confidence).
    Summary numbers are medians so one viral video can't skew a cluster.
    """
    def channel_count(group: list[int]) -> int:
        return len({videos[i]["channel_id"] for i in group})

    has_topics = topic_embeddings is not None and len(topic_embeddings) > 0

    def centroid_fit(group: list[int]) -> float:
        if not has_topics:
            return 0.0
        centroid = embeddings[group].mean(axis=0)
        centroid = centroid / (np.linalg.norm(centroid) or 1.0)
        return float(max(0.0, (topic_embeddings @ centroid).max()))

    fit = {tuple(g): centroid_fit(g) for g in clusters}
    if has_topics:
        relevant = [g for g in clusters if fit[tuple(g)] >= MIN_CREATOR_FIT]
        print(f"[ResearchAgent] Creator-fit gate (≥ {MIN_CREATOR_FIT}): "
              f"{len(clusters)} → {len(relevant)} clusters")
        clusters = relevant

    multi_channel = [g for g in clusters if channel_count(g) >= MIN_CLUSTER_CHANNELS]
    strong = [g for g in multi_channel if len(g) >= MIN_CLUSTER_SIZE]
    weak = [g for g in multi_channel if MIN_WEAK_CLUSTER_SIZE <= len(g) < MIN_CLUSTER_SIZE]
    tiers = [(g, False) for g in strong] + [(g, True) for g in weak]
    if not tiers:
        print("[ResearchAgent] ⚠ No multi-channel cluster found — low confidence")
        fallback = [g for g in clusters if len(g) >= 2] or clusters
        tiers = [(g, True) for g in fallback]

    max_channels = max(channel_count(g) for g, _ in tiers) if tiers else 1
    trends = []
    for group, low_confidence in tiers:
        members = sorted((videos[i] for i in group), key=lambda v: v["video_score"], reverse=True)
        creator_fit = fit[tuple(group)]
        strength = statistics.median(v["video_score"] for v in members)
        spread = channel_count(group) / max_channels
        trend_score = W_STRENGTH * strength + W_SPREAD * spread + W_FIT * creator_fit
        median_outlier = statistics.median(v["outlier"] for v in members)

        trends.append({
            "trend_score": round(trend_score, 4),
            "creator_fit": round(creator_fit, 4),
            "median_velocity": round(statistics.median(v["velocity"] for v in members), 1),
            "median_outlier": round(median_outlier, 3),
            "median_engagement": round(statistics.median(v["engagement"] for v in members), 4),
            "video_count": len(members),
            "channel_count": channel_count(group),
            "low_confidence": low_confidence or median_outlier < OVERPERFORM_OUTLIER,
            "titles": [v["title"] for v in members[:TITLES_FOR_LABELING]],
            "evidence": [{
                "video_id": v["video_id"],
                "url": f"https://www.youtube.com/shorts/{v['video_id']}",
                "title": v["title"],
                "channel": v["channel"],
                "views": v["views"],
                "subscribers": v["subscribers"],
                "outlier": round(v["outlier"], 3),
                "velocity": round(v["velocity"], 1),
                "published_hours_ago": v["hours_since_upload"],
                "reuploads": v.get("duplicate_count", 0),
            } for v in members[:EVIDENCE_PER_TREND]],
        })

    # strong trends first, then weak; each tier by score
    trends.sort(key=lambda t: (t["low_confidence"], -t["trend_score"]))
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


def _why_trending(trend: dict) -> str:
    """Factual summary built only from measured numbers."""
    return (f"{trend['video_count']} Shorts from {trend['channel_count']} channels in the last "
            f"{SEARCH_PUBLISHED_DAYS} days; the typical one gets "
            f"{_format_count(trend['median_velocity'])} views/hour and "
            f"{trend['median_outlier']:.1f}× its channel's subscriber count.")


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
    prompt = (
        "These YouTube Shorts are all trending around one topic:\n"
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

def run_research(profile: dict, niche: str, top_k: int = TOP_K_TRENDS,
                 now: datetime | None = None,
                 api_key: str | None = None) -> dict:
    """
    Full research run. Returns:
      { "trends": [trend, ...], "queries": [...], "source": str, "error": str | None }

    Never raises: failures produce an empty trend list and an error message.
    """
    now = now or datetime.now(timezone.utc)
    api_key = api_key if api_key is not None else os.getenv("YOUTUBE_API_KEY", "")

    queries = generate_queries(profile, niche)
    print(f"[ResearchAgent] Queries: {queries}")
    if not api_key:
        return {"trends": [], "queries": queries, "source": "none",
                "error": "YOUTUBE_API_KEY not set"}

    try:
        videos = collect_videos(queries, api_key, now)
    except requests.RequestException as e:
        status = getattr(getattr(e, "response", None), "status_code", 0)
        return {"trends": [], "queries": queries, "source": "none",
                "error": f"YouTube API error (HTTP {status}): {e}"}

    if not videos:
        return {"trends": [], "queries": queries, "source": "youtube_data_api",
                "error": "No usable Shorts found for these queries"}

    score_videos(videos, now)
    embeddings = embed_texts([video_text(v) for v in videos])
    before = len(videos)
    videos, embeddings = collapse_near_duplicates(videos, embeddings)
    print(f"[ResearchAgent] Near-duplicates collapsed: {before} → {len(videos)} distinct videos")
    clusters = cluster_embeddings(embeddings)
    print(f"[ResearchAgent] {len(clusters)} clusters, sizes: "
          f"{sorted((len(c) for c in clusters), reverse=True)[:10]}")

    trends = build_trends(videos, embeddings, clusters,
                          _profile_embedding(profile, niche))[:top_k]
    if not trends:
        return {"trends": [], "queries": queries, "source": "youtube_data_api",
                "error": f"No trending cluster matched the creator's topics "
                         f"(creator_fit < {MIN_CREATOR_FIT})"}
    label_trends(trends, niche)
    return {"trends": trends, "queries": queries, "source": "youtube_data_api", "error": None}


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
            "engagement_rate": best["median_engagement"],
            "outlier": best["median_outlier"],
        },
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
