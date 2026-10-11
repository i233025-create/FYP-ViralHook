"""
research_agent.py — LangGraph Research Agent Node (YouTube Data API v3)
========================================================================
This node runs BEFORE the Scripting Agent. It:
  1. Expands creator_niche into 5-8 related keywords (static, no LLM call).
  2. Calls YouTube Data API search.list per keyword to find recent videos
     (published in last 5 days, ordered by viewCount, maxResults=20).
  3. Calls videos.list (batched) for statistics: viewCount, likeCount,
     commentCount, publishedAt.
  4. Scores each video:
       velocity         = viewCount / hours_since_published
       engagement_rate  = (likeCount + commentCount) / viewCount
       trend_score      = 0.6 * norm_velocity + 0.4 * norm_engagement
  5. Clusters top-scoring video titles by TF-IDF n-gram overlap.
  6. Picks the top cluster and writes research_output to pipeline state.

Fallback:
  If YouTube API quota is exceeded or all calls fail, falls back to
  LLM-generated topic suggestion. The graph never crashes.

Caching:
  API responses cached in pipeline/cache/ as JSON files (TTL = 6 hours).
  Key = hash(keyword + date). Avoids burning quota on repeated dev runs.

Quota cost per full run:
  search.list  = 100 units × ~5 keywords = ~500 units
  videos.list  = 1 unit × batched IDs    = ~5 units
  Total        ≈ 505 units / run  (free quota = 10,000/day → ~19 runs/day)
"""

from __future__ import annotations

import json
import os
import hashlib
import math
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Load .env — check both locations
load_dotenv(Path(__file__).parent.parent.parent / "module1_style_extraction" / ".env")
load_dotenv(Path(__file__).parent.parent.parent / ".env")

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from pipeline.state import PipelineState

# ─── Configuration ─────────────────────────────────────────────────────────────
CACHE_DIR = Path(__file__).parent.parent / "cache"
CACHE_TTL_HOURS = 6
MAX_KEYWORDS = 8
SEARCH_MAX_RESULTS = 20       # YouTube search results per keyword
SEARCH_PUBLISHED_DAYS = 5     # Only videos published in last N days
TOP_N_FOR_CLUSTERING = 30     # Top N scored videos to cluster (was 10 — too few)
CLUSTER_SIM_THRESHOLD = 0.06  # Jaccard threshold (was 0.12 — too strict for short titles)

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"


# ─── Static Keyword Expansion ──────────────────────────────────────────────────
NICHE_KEYWORD_MAP: dict[str, list[str]] = {
    "personal growth":    ["self improvement tips", "morning routine productivity",
                           "growth mindset", "discipline habits", "stoicism daily",
                           "consistency motivation", "mindset shift"],
    "self improvement":   ["self improvement tips", "morning routine productivity",
                           "growth mindset", "discipline habits", "stoicism daily",
                           "consistency motivation", "mindset shift"],
    "motivation":         ["motivation techniques", "mindset shifts", "daily discipline",
                           "success habits", "mental toughness", "self discipline"],
    "personal finance":   ["investing for beginners", "budgeting tips",
                           "passive income ideas", "financial freedom",
                           "savings strategies", "compound interest", "money habits"],
    "finance":            ["investing for beginners", "stock market basics",
                           "financial freedom", "budgeting apps", "money tips"],
    "crypto":             ["bitcoin price prediction", "ethereum news",
                           "defi explained", "crypto investing", "altcoin gems"],
    "tech":               ["AI tools", "best productivity apps", "ChatGPT tips",
                           "tech news", "software review", "AI automation"],
    "technology":         ["AI tools", "best productivity apps", "ChatGPT tips",
                           "tech news", "software review", "AI automation"],
    "ai":                 ["ChatGPT tips", "AI image generation",
                           "artificial intelligence news", "LLM explained", "AI tools"],
    "health":             ["workout routine", "healthy eating habits",
                           "mental health tips", "sleep optimization", "weight loss tips"],
    "fitness":            ["workout routine beginners", "home workout",
                           "fat loss tips", "muscle building", "gym motivation"],
    "wellness":           ["mindfulness meditation", "sleep hygiene",
                           "stress reduction", "mental health", "healthy lifestyle"],
    "business":           ["startup tips", "entrepreneur mindset",
                           "side hustle ideas", "small business marketing",
                           "business growth", "online business"],
    "entrepreneurship":   ["startup ideas", "side hustle success",
                           "entrepreneur daily routine", "business mistakes",
                           "scaling a business", "passive income"],
    "marketing":          ["social media marketing tips", "instagram growth",
                           "content strategy", "digital marketing", "brand building"],
    "education":          ["study techniques", "learning hacks",
                           "online courses", "skill development", "career advice"],
    "history":            ["history facts", "historical events today",
                           "ancient civilizations", "world history", "historical mysteries"],
    "science":            ["science facts", "space exploration news",
                           "biology discoveries", "physics explained"],
    "lifestyle":          ["minimalist living", "morning routine ideas",
                           "productivity hacks", "life advice", "aesthetic lifestyle"],
    "beauty":             ["skincare routine", "makeup tutorial", "beauty tips",
                           "skincare ingredients", "foundation routine",
                           "glass skin routine", "glow up tips"],
    "skincare":           ["skincare routine", "best skincare products",
                           "glass skin routine", "acne tips", "skincare ingredients"],
    "makeup":             ["makeup tutorial", "everyday makeup look",
                           "drugstore makeup", "foundation routine", "eye makeup"],
    "fashion":            ["outfit ideas", "fashion trends", "sustainable fashion",
                           "style tips", "wardrobe essentials"],
    "food":               ["easy recipes", "meal prep ideas", "food trends",
                           "healthy cooking", "cooking tips beginners"],
    "gaming":             ["gaming news", "best games", "game review",
                           "esports highlights", "gaming tips"],
    "default":            ["trending topics today", "viral content ideas",
                           "social media trends", "content creation tips",
                           "instagram reels ideas", "viral shorts"],
}


def _expand_keywords(niche: str) -> list[str]:
    """
    Map a creator niche to related YouTube search keywords.
    Uses substring matching — no LLM call needed.
    """
    niche_lower = niche.lower().strip()

    if niche_lower in NICHE_KEYWORD_MAP:
        return NICHE_KEYWORD_MAP[niche_lower][:MAX_KEYWORDS]

    for key, keywords in NICHE_KEYWORD_MAP.items():
        if key in niche_lower or niche_lower in key:
            return keywords[:MAX_KEYWORDS]

    niche_words = set(niche_lower.split())
    for key, keywords in NICHE_KEYWORD_MAP.items():
        if niche_words & set(key.split()):
            return keywords[:MAX_KEYWORDS]

    fallback = NICHE_KEYWORD_MAP["default"].copy()
    fallback.insert(0, niche)
    return fallback[:MAX_KEYWORDS]


# ─── Cache Utilities ───────────────────────────────────────────────────────────

def _cache_key(keyword: str, date_str: str) -> str:
    return hashlib.md5(f"{keyword}_{date_str}".encode()).hexdigest()


def _load_cache(keyword: str) -> list | None:
    date_str = datetime.now().strftime("%Y-%m-%d")
    path = CACHE_DIR / f"{_cache_key(keyword, date_str)}.json"
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


def _save_cache(keyword: str, data: list) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    path = CACHE_DIR / f"{_cache_key(keyword, date_str)}.json"
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"cached_at": datetime.now().isoformat(), "data": data}, f, indent=2)
    except IOError:
        pass


# ─── YouTube API Calls ─────────────────────────────────────────────────────────

def _published_after_iso() -> str:
    """Return ISO 8601 timestamp for N days ago (UTC)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=SEARCH_PUBLISHED_DAYS)
    return cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")


def _search_videos(keyword: str, api_key: str) -> list[str]:
    """
    Call YouTube search.list to find recent videos for a keyword.

    Returns a list of video IDs (up to SEARCH_MAX_RESULTS).
    Costs 100 quota units per call.

    Raises:
        requests.HTTPError: On quota exceeded (403) or other API errors.
    """
    # Check cache first
    cached = _load_cache(f"search_{keyword}")
    if cached is not None:
        print(f"  [cache] search results for '{keyword}'")
        return cached

    params = {
        "part": "id",
        "q": keyword,
        "type": "video",
        "publishedAfter": _published_after_iso(),
        "order": "viewCount",
        "maxResults": SEARCH_MAX_RESULTS,
        "key": api_key,
    }

    response = requests.get(YOUTUBE_SEARCH_URL, params=params, timeout=15)

    # Raise for HTTP errors (quota exceeded = 403, invalid key = 400)
    response.raise_for_status()

    data = response.json()
    video_ids = [item["id"]["videoId"] for item in data.get("items", [])
                 if item.get("id", {}).get("videoId")]

    _save_cache(f"search_{keyword}", video_ids)
    return video_ids


def _get_video_stats(video_ids: list[str], api_key: str) -> list[dict]:
    """
    Call YouTube videos.list (batched, max 50 IDs per request) to get
    statistics and snippet for a list of video IDs.

    Returns list of dicts with: id, title, channel, viewCount, likeCount,
    commentCount, publishedAt.
    Costs 1 quota unit per batch (very cheap).
    """
    if not video_ids:
        return []

    # Check cache
    batch_key = f"stats_{'_'.join(sorted(video_ids[:5]))}"
    cached = _load_cache(batch_key)
    if cached is not None:
        return cached

    results = []
    # YouTube allows max 50 IDs per videos.list call
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        params = {
            "part": "statistics,snippet",
            "id": ",".join(batch),
            "key": api_key,
        }
        response = requests.get(YOUTUBE_VIDEOS_URL, params=params, timeout=15)
        response.raise_for_status()

        for item in response.json().get("items", []):
            stats = item.get("statistics", {})
            snippet = item.get("snippet", {})
            # Truncate description to first 200 chars — enough for topic signal,
            # avoids bloating the keyword sets with irrelevant long-form text.
            description = snippet.get("description", "")[:200]
            results.append({
                "video_id": item["id"],
                "title": snippet.get("title", ""),
                "description": description,
                "channel": snippet.get("channelTitle", ""),
                "publishedAt": snippet.get("publishedAt", ""),
                "viewCount": int(stats.get("viewCount", 0)),
                "likeCount": int(stats.get("likeCount", 0)),
                "commentCount": int(stats.get("commentCount", 0)),
            })

    _save_cache(batch_key, results)
    return results


# ─── Trend Scoring ─────────────────────────────────────────────────────────────

def _hours_since_published(published_at: str) -> float:
    """Calculate hours between video publish time and now."""
    try:
        pub_time = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ")
        pub_time = pub_time.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - pub_time
        hours = delta.total_seconds() / 3600
        return max(hours, 0.5)  # Minimum 0.5 hours to avoid division by near-zero
    except (ValueError, TypeError):
        return 24.0  # Default to 24 hours if parsing fails


def _score_videos(videos: list[dict]) -> list[dict]:
    """
    Score videos by trend strength using velocity + engagement.

    Formulas (from spec):
      velocity         = viewCount / hours_since_published
      engagement_rate  = (likeCount + commentCount) / viewCount
      trend_score      = 0.6 * norm_velocity + 0.4 * norm_engagement

    Both metrics are min-max normalised across the full candidate set.
    """
    if not videos:
        return []

    # Compute raw metrics
    for v in videos:
        hours = _hours_since_published(v.get("publishedAt", ""))
        view_count = max(v.get("viewCount", 0), 1)  # avoid div by zero
        v["velocity"] = v["viewCount"] / hours
        v["engagement_rate"] = (
            (v.get("likeCount", 0) + v.get("commentCount", 0)) / view_count
        )

    # Min-max normalisation
    velocities = [v["velocity"] for v in videos]
    engagements = [v["engagement_rate"] for v in videos]

    v_min, v_max = min(velocities), max(velocities)
    e_min, e_max = min(engagements), max(engagements)
    v_range = v_max - v_min if v_max != v_min else 1.0
    e_range = e_max - e_min if e_max != e_min else 1.0

    for v in videos:
        norm_v = (v["velocity"] - v_min) / v_range
        norm_e = (v["engagement_rate"] - e_min) / e_range
        v["trend_score"] = round(0.6 * norm_v + 0.4 * norm_e, 4)

    videos.sort(key=lambda x: x["trend_score"], reverse=True)
    return videos


# ─── Topic Clustering ──────────────────────────────────────────────────────────

# Keyword overlap: we cluster on n-grams extracted from title + description
# rather than raw title similarity, because YouTube titles are often clickbait
# and don't share n-grams even when covering the same topic.

# Words to strip when extracting topic keywords from titles.
# These are high-frequency words that appear in many unrelated titles
# and would create false similarity.
_TITLE_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "it", "this", "that", "my", "your",
    "i", "me", "we", "you", "he", "she", "they", "was", "are", "be",
    "have", "has", "had", "do", "did", "will", "would", "could", "should",
    "how", "what", "why", "when", "who", "just", "get", "got", "day",
    "life", "time", "new", "one", "like", "make", "know", "want", "need",
    "video", "shorts", "youtube", "watch", "subscribe", "comment",
}


def _extract_topic_keywords(video: dict) -> set[str]:
    """
    Extract meaningful content keywords from a video's title + description.

    Using both fields gives far richer signal than title alone — two videos
    about "morning routines" may have completely different titles but share
    keywords like "productive", "routine", "morning" in their descriptions.

    Strips stopwords, emoji, hashtags, and punctuation.
    """
    import re
    # Combine title (weighted ×2 for importance) + description
    text = video.get("title", "") + " " + video.get("title", "") + " " + video.get("description", "")

    cleaned = re.sub(r"#\w+", "", text)
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    words = {
        w.lower() for w in cleaned.split()
        if len(w) > 3 and w.lower() not in _TITLE_STOPWORDS
    }
    return words


def _keyword_overlap_score(set_a: set[str], set_b: set[str]) -> float:
    """
    Jaccard similarity between two keyword sets.
    Returns 0.0 if either set is empty.
    """
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def _cluster_videos(scored_videos: list[dict], niche: str) -> dict:
    """
    Cluster top-scoring videos by topic keyword overlap, then pick the
    LARGEST coherent cluster (most videos about the same topic) weighted
    by combined trend score.

    This fixes the "clickbait outlier" problem where a single high-velocity
    video about an unrelated topic wins just because it has the highest
    trend_score. A real trending topic will have multiple videos covering it.

    Algorithm:
      1. Take top TOP_N_FOR_CLUSTERING scored videos.
      2. Extract content keywords from each title (strip stopwords/hashtags).
      3. Build a keyword-overlap similarity matrix.
      4. Greedy-cluster: group videos with Jaccard similarity > threshold.
      5. Score each cluster by: sum(trend_score) * len(cluster)^0.5
         (rewards coherent clusters over single high-scoring outliers).
      6. Pick the highest-scoring cluster.
      7. Within that cluster, synthesise a topic name from shared keywords
         rather than using one raw video title.

    Args:
        scored_videos: Output of _score_videos(), sorted by trend_score desc.
        niche: Creator niche string — used as fallback topic name.

    Returns:
        research_output dict ready for pipeline state.
    """
    if not scored_videos:
        return _format_output(scored_videos[0], [], niche) if scored_videos else None

    top = scored_videos[:TOP_N_FOR_CLUSTERING]

    # ── Step 1: Extract keywords from each title + description ────────────────
    keyword_sets = [_extract_topic_keywords(v) for v in top]

    # ── Step 2: Build similarity matrix ───────────────────────────────────────
    n = len(top)
    sim_matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            score = _keyword_overlap_score(keyword_sets[i], keyword_sets[j])
            sim_matrix[i][j] = score
            sim_matrix[j][i] = score

    # ── Step 3: Greedy clustering ──────────────────────────────────────────────
    OVERLAP_THRESHOLD = 0.10

    clusters: list[list[int]] = []
    assigned: set[int] = set()

    for i in range(n):
        if i in assigned:
            continue
        cluster = [i]
        assigned.add(i)
        for j in range(i + 1, n):
            if j not in assigned and sim_matrix[i][j] >= OVERLAP_THRESHOLD:
                cluster.append(j)
                assigned.add(j)
        clusters.append(cluster)

    # ── Cluster diagnostics (always printed so behaviour is observable) ────────
    cluster_sizes = sorted([len(c) for c in clusters], reverse=True)
    size_distribution = {}
    for s in cluster_sizes:
        size_distribution[s] = size_distribution.get(s, 0) + 1

    print(f"[ResearchAgent] Clustering: {len(clusters)} clusters from {n} videos")
    print(f"[ResearchAgent] Size distribution: {size_distribution} "
          f"(e.g. {{3: 2}} = two clusters of size 3)")
    print(f"[ResearchAgent] Cluster sizes (desc): {cluster_sizes[:10]}")

    # ── Step 4: Score each cluster ─────────────────────────────────────────────
    def cluster_score(cluster: list[int]) -> float:
        total_trend = sum(top[i]["trend_score"] for i in cluster)
        size_bonus = len(cluster) ** 0.5
        return total_trend * size_bonus

    # ── Step 5: Apply minimum cluster size threshold ──────────────────────────
    # A topic is only "confirmed trending" if >= MIN_CLUSTER_SIZE independent
    # videos cover it. A single popular video is not a trend signal.
    MIN_CLUSTER_SIZE = 2

    qualifying_clusters = [c for c in clusters if len(c) >= MIN_CLUSTER_SIZE]
    low_confidence = False

    if qualifying_clusters:
        best_cluster = max(qualifying_clusters, key=cluster_score)
        print(f"[ResearchAgent] Qualifying clusters (size>={MIN_CLUSTER_SIZE}): "
              f"{len(qualifying_clusters)} — picking best (size={len(best_cluster)})")
    else:
        # No cluster has >= MIN_CLUSTER_SIZE videos — fall back to best single-video
        # cluster but flag the result so downstream nodes know it's weak signal.
        best_cluster = max(clusters, key=cluster_score)
        low_confidence = True
        print(f"[ResearchAgent] ⚠ No cluster met size>={MIN_CLUSTER_SIZE} threshold "
              f"— using best single-video cluster. low_confidence=True")
    cluster_videos = [top[i] for i in best_cluster]

    # ── Step 5: Synthesise topic name from shared keywords ────────────────────
    # Instead of using one raw clickbait title, find the most common keywords
    # across all videos in the cluster and build a clean topic label.
    all_kw_sets = [keyword_sets[i] for i in best_cluster]
    shared_keywords = set.intersection(*all_kw_sets) if len(all_kw_sets) > 1 else all_kw_sets[0]

    if shared_keywords and len(shared_keywords) >= 2:
        # Use shared keywords to name the topic
        topic_name = " ".join(sorted(shared_keywords, key=len, reverse=True)[:4])
        topic_name = topic_name.title()
    else:
        # Fall back to the title of the highest trend_score video in the cluster.
        # Clean up the raw title aggressively:
        import re
        best_in_cluster = max(cluster_videos, key=lambda v: v["trend_score"])
        raw_title = best_in_cluster["title"]

        # Remove hashtags
        clean_title = re.sub(r"#\w+", "", raw_title)
        # Remove emoji and non-ASCII symbols
        clean_title = re.sub(r"[^\x00-\x7F]", "", clean_title)
        # Replace underscores with spaces (common in YouTube titles)
        clean_title = clean_title.replace("_", " ")
        # Remove known noise words that appear in viral/shorts titles
        noise_words = {"shorts", "shortsfeed", "viral", "video", "trending",
                       "reels", "tiktok", "youtube", "subscribe", "like", "share"}
        words = [w for w in clean_title.split() if w.lower() not in noise_words]
        clean_title = " ".join(words).strip()
        # Strip leftover punctuation at edges
        clean_title = re.sub(r"^[\W]+|[\W]+$", "", clean_title)
        # Collapse multiple spaces
        clean_title = re.sub(r"\s+", " ", clean_title).strip()

        # If title was all hashtags/noise and cleaned to nothing,
        # synthesise a topic name from the cluster's shared keywords instead
        if len(clean_title) < 5:
            # Union of all keywords across cluster — pick most common ones
            all_words: list[str] = []
            for kw_set in all_kw_sets:
                all_words.extend(kw_set)
            if all_words:
                from collections import Counter
                common = [w for w, _ in Counter(all_words).most_common(4)]
                clean_title = " ".join(common).title()
            else:
                clean_title = niche  # absolute last resort

        topic_name = clean_title

    # ── Step 6: Format output ─────────────────────────────────────────────────
    best_video = max(cluster_videos, key=lambda v: v["trend_score"])

    supporting = [
        {
            "video_title": v["title"],
            "channel": v["channel"],
            "views": v["viewCount"],
            "published_hours_ago": round(_hours_since_published(v["publishedAt"]), 1),
        }
        for v in cluster_videos
        if v["video_id"] != best_video["video_id"]
    ][:3]  # max 3 supporting videos

    return {
        "topic": topic_name,
        "trend_score": round(best_video["trend_score"], 4),
        "trend_signals": {
            "velocity": round(best_video.get("velocity", 0.0), 2),
            "engagement_rate": round(best_video.get("engagement_rate", 0.0), 4),
        },
        "niche": niche,
        "supporting_evidence": supporting,
        "related_keywords": [],  # filled by caller
        "cluster_size": len(cluster_videos),
        "low_confidence": low_confidence,
        "source": "youtube_data_api",
    }


def _format_output(best_video: dict, cluster_videos: list[dict], niche: str) -> dict:
    """Minimal format for single-video fallback."""
    return {
        "topic": best_video["title"],
        "trend_score": best_video.get("trend_score", 0.0),
        "trend_signals": {
            "velocity": round(best_video.get("velocity", 0.0), 2),
            "engagement_rate": round(best_video.get("engagement_rate", 0.0), 4),
        },
        "niche": niche,
        "supporting_evidence": [],
        "related_keywords": [],
        "cluster_size": 1,
        "source": "youtube_data_api",
    }


# ─── Fallback (LLM-based) ──────────────────────────────────────────────────────

def _llm_fallback_topic(niche: str, keywords: list[str]) -> dict:
    """
    LLM-based fallback when YouTube API is unavailable/quota exceeded.
    Uses Groq to suggest a plausible trending topic.
    """
    try:
        from langchain_groq import ChatGroq
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import JsonOutputParser

        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set")

        llm = ChatGroq(api_key=api_key, model_name="openai/gpt-oss-20b",
                       temperature=0.7, max_tokens=512)

        prompt = ChatPromptTemplate.from_template(
            """You are a social media trend analyst. Today is {date}.
Niche: "{niche}". Keywords: {keywords}.
Suggest the single most compelling trending topic for a short-form video right now.
Output ONLY valid JSON: {{"topic": "string", "trend_score": 0.8, 
"trend_signals": {{"velocity": 0.7, "engagement_rate": 0.8}}}}"""
        )

        result = (prompt | llm | JsonOutputParser()).invoke({
            "date": datetime.now().strftime("%B %d, %Y"),
            "niche": niche,
            "keywords": json.dumps(keywords[:5]),
        })

        result.setdefault("topic", f"trending topic in {niche}")
        result.setdefault("trend_score", 0.75)
        result.setdefault("trend_signals", {"velocity": 0.7, "engagement_rate": 0.7})
        return result

    except Exception as e:
        # Final static fallback
        static_map = {
            "personal growth": "discipline habits that changed my life",
            "personal finance": "investing mistakes beginners make",
            "tech": "AI tools replacing jobs in 2024",
            "fitness": "home workout routine no equipment",
            "business": "side hustle ideas that actually work",
        }
        niche_lower = niche.lower()
        topic = next((v for k, v in static_map.items() if k in niche_lower),
                     f"trending topics in {niche}")
        return {
            "topic": topic,
            "trend_score": 0.0,
            "trend_signals": {"velocity": 0.0, "engagement_rate": 0.0},
        }


# ─── LangGraph Node ────────────────────────────────────────────────────────────

def research_agent(state: PipelineState) -> dict[str, Any]:
    """
    LangGraph node: Research Agent.

    Reads creator_niche from state, queries YouTube Data API to find the
    top trending video topic in that niche, and writes research_output.

    Returns a partial state update dict — LangGraph merges it automatically.
    """
    niche = state.get("creator_niche", "")
    creator_id = state.get("creator_id", "unknown")

    print(f"\n[ResearchAgent] creator_id={creator_id}, niche='{niche}'")

    api_key = os.getenv("YOUTUBE_API_KEY", "")
    if not api_key:
        print("[ResearchAgent] YOUTUBE_API_KEY not found — using LLM fallback")
        keywords = _expand_keywords(niche)
        result = _llm_fallback_topic(niche, keywords)
        result["niche"] = niche
        result["related_keywords"] = keywords
        result["supporting_evidence"] = []
        return {
            "research_output": result,
            "research_error": "YOUTUBE_API_KEY not set — used LLM fallback",
        }

    try:
        # ── Step 1: Keyword expansion ──────────────────────────────────────
        keywords = _expand_keywords(niche)
        print(f"[ResearchAgent] Keywords: {keywords}")

        # ── Step 2: Search YouTube for each keyword ────────────────────────
        all_video_ids: list[str] = []
        for i, kw in enumerate(keywords):
            if i > 0:
                time.sleep(0.3)  # Small delay between search calls
            try:
                ids = _search_videos(kw, api_key)
                print(f"[ResearchAgent] '{kw}' → {len(ids)} videos")
                all_video_ids.extend(ids)
            except requests.HTTPError as e:
                status = e.response.status_code if e.response else 0
                if status == 403:
                    # Quota exceeded — stop searching, use what we have
                    print(f"[ResearchAgent] Quota exceeded on '{kw}' — stopping search")
                    break
                print(f"[ResearchAgent] Search failed for '{kw}': {e}")

        # Deduplicate video IDs (same video can appear across keyword searches)
        unique_ids = list(dict.fromkeys(all_video_ids))
        print(f"[ResearchAgent] Total unique videos: {len(unique_ids)}")

        if not unique_ids:
            raise ValueError("No videos found for any keyword")

        # ── Step 3: Fetch video statistics ────────────────────────────────
        videos = _get_video_stats(unique_ids, api_key)
        print(f"[ResearchAgent] Got stats for {len(videos)} videos")

        # ── Step 4: Score by velocity + engagement ────────────────────────
        scored = _score_videos(videos)
        if scored:
            print(f"[ResearchAgent] Top video: '{scored[0]['title'][:60]}' "
                  f"(score={scored[0]['trend_score']})")

        # ── Step 5: Cluster and pick best topic ───────────────────────────
        research_output = _cluster_videos(scored, niche)
        if not research_output:
            raise ValueError("Topic clustering returned no result")

        # Enrich with niche and keywords
        research_output["niche"] = niche
        research_output["related_keywords"] = keywords

        print(f"[ResearchAgent] Selected topic: '{research_output['topic'][:70]}'")

        return {
            "research_output": research_output,
            "research_error": None,
        }

    except requests.HTTPError as e:
        status = e.response.status_code if e.response else 0
        error_msg = f"YouTube API error (HTTP {status}): {e}"
        print(f"[ResearchAgent] {error_msg} — using LLM fallback")
        keywords = _expand_keywords(niche)
        fallback = _llm_fallback_topic(niche, keywords)
        fallback["niche"] = niche
        fallback["related_keywords"] = keywords
        fallback.setdefault("supporting_evidence", [])
        fallback["source"] = "llm_fallback"
        return {
            "research_output": fallback,
            "research_error": error_msg,
        }

    except Exception as e:
        error_msg = f"ResearchAgent failed: {str(e)}"
        print(f"[ResearchAgent] ERROR: {error_msg} — using LLM fallback")
        keywords = _expand_keywords(niche)
        fallback = _llm_fallback_topic(niche, keywords)
        fallback["niche"] = niche
        fallback["related_keywords"] = keywords
        fallback.setdefault("supporting_evidence", [])
        fallback["source"] = "llm_fallback"
        return {
            "research_output": fallback,
            "research_error": error_msg,
        }
