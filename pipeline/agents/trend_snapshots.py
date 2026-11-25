"""
trend_snapshots.py — daily view snapshots, so "growing" is measured, not guessed.

Without snapshots, growth comes from one 14-day search sample (more uploads
in the last 3 days than before), and E1 showed that estimate is unreliable.
With snapshots, every run stores the view count of every video it saw, and the
next run (≥ MIN_GAP_HOURS later) can measure how fast each video is gaining
views *now* compared with its own lifetime average:

    acceleration = (views gained per day since the last snapshot + s)
                 / (average views per day over the video's life until then + s)

A normal Short decays (acceleration < 1). A video riding a topic that is
taking off keeps or speeds up its pace (acceleration ≥ 1). The Research
Agent compares a cluster's median acceleration with the whole niche's, so
the normal decay cancels out the same way the search bias does in
relative_growth().

Files: pipeline/cache/snapshots/<niche-key>/<YYYY-MM-DD>.json
  {"videos": {video_id: {"views": int, "t": iso time, "published_at": iso,
                          "channel_id": str}}}
One file per UTC day; a second run on the same day updates it. The folder is
git-ignored: it holds other creators' video stats.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

MIN_GAP_HOURS = 20        # compare with a snapshot at least this old
HISTORY_DAYS = 8          # look back this far for snapshots / tracked videos
MIN_AGE_DAYS = 0.5        # lifetime rate of a video younger than this is noise
SMOOTHING_PER_DAY = 10.0  # views/day added to both rates: tiny videos can't spike

_ISO = "%Y-%m-%dT%H:%M:%SZ"


def niche_key(niche: str) -> str:
    """'Beginner fitness & home workouts' → 'beginner-fitness-home-workouts'."""
    return re.sub(r"[^a-z0-9]+", "-", niche.lower()).strip("-")[:60] or "default"


def _parse(ts: str) -> datetime | None:
    try:
        return datetime.strptime(ts, _ISO).replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def load_history(root: Path, key: str, now: datetime,
                 days: int = HISTORY_DAYS) -> list[dict[str, dict]]:
    """Snapshots of the last `days` days, newest first (today's included)."""
    folder = root / key
    if not folder.exists():
        return []
    out = []
    for path in sorted(folder.glob("*.json"), reverse=True):
        try:
            day = datetime.strptime(path.stem, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if day < (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0):
            continue
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")).get("videos", {}))
        except (OSError, json.JSONDecodeError):
            continue
    return out


def tracked_ids(history: list[dict[str, dict]]) -> set[str]:
    return {vid for snap in history for vid in snap}


def save_snapshot(root: Path, key: str, now: datetime, videos: list[dict]) -> Path:
    """Merge the view counts of `videos` into today's snapshot file."""
    folder = root / key
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{now.strftime('%Y-%m-%d')}.json"
    data: dict = {"videos": {}}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    stamp = now.strftime(_ISO)
    for v in videos:
        if v.get("video_id") and v.get("views") is not None:
            data.setdefault("videos", {})[v["video_id"]] = {
                "views": int(v["views"]), "t": stamp,
                "published_at": v.get("published_at", ""),
                "channel_id": v.get("channel_id", ""),
            }
    path.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return path


def previous_point(video_id: str, now: datetime,
                   history: list[dict[str, dict]]) -> dict | None:
    """Newest snapshot entry of this video that is at least MIN_GAP_HOURS old."""
    cutoff = now - timedelta(hours=MIN_GAP_HOURS)
    best, best_t = None, None
    for snap in history:
        entry = snap.get(video_id)
        t = _parse(entry["t"]) if entry else None
        if t is not None and t <= cutoff and (best_t is None or t > best_t):
            best, best_t = entry, t
    return best


def acceleration(video_id: str, views_now: int, published_at: str, now: datetime,
                 history: list[dict[str, dict]]) -> float | None:
    """Current daily view gain ÷ lifetime daily average (see module docstring)."""
    prev = previous_point(video_id, now, history)
    published = _parse(published_at)
    if prev is None or published is None:
        return None
    t_prev = _parse(prev["t"])
    gap_days = (now - t_prev).total_seconds() / 86400
    age_prev_days = max((t_prev - published).total_seconds() / 86400, MIN_AGE_DAYS)
    recent_rate = max(views_now - prev["views"], 0) / gap_days
    lifetime_rate = prev["views"] / age_prev_days
    return (recent_rate + SMOOTHING_PER_DAY) / (lifetime_rate + SMOOTHING_PER_DAY)
