"""
ablation_fixes.py — effect of each V1 fix on the SAME data.

Runs the YouTube Research Agent once per setting on one shared data pull
(searches come from the 6-hour cache, video/channel details are fetched once
and reused), so differences come only from the settings:

  old       floor 1000, cluster distance 0.6, no English-word filter
  +floor    fix 1: SUBSCRIBER_FLOOR 5000
  +cluster  fix 2: CLUSTER_DISTANCE_THRESHOLD 0.5
  +english  fix 3: English-word filter on titles
  new       all three

Usage:
  python experiments/trend_e1/ablation_fixes.py --queries-from 2026-11-18
Writes results/ablation_<date>.md and results/ablation_<date>.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))

from pipeline.agents import research_agent as ra  # noqa: E402
from run_e1 import load_niches, previous_queries, RESULTS  # noqa: E402

SETTINGS = {
    "old":      dict(floor=1000, dist=0.6, english=False),
    "+floor":   dict(floor=5000, dist=0.6, english=False),
    "+cluster": dict(floor=1000, dist=0.5, english=False),
    "+english": dict(floor=1000, dist=0.6, english=True),
    "new":      dict(floor=5000, dist=0.5, english=True),
}


def memoise(fn):
    seen: dict = {}

    def wrapper(ids, *args):
        key = tuple(ids)
        if key not in seen:
            seen[key] = fn(ids, *args)
        return [dict(x) if isinstance(x, dict) else x for x in seen[key]] \
            if isinstance(seen[key], list) else dict(seen[key])
    return wrapper


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--queries-from", required=True)
    p.add_argument("--niches", nargs="+", default=None)
    args = p.parse_args()

    ra._fetch_video_details = memoise(ra._fetch_video_details)
    ra._fetch_subscribers = memoise(ra._fetch_subscribers)
    ra._fetch_channel_info = memoise(ra._fetch_channel_info)
    ra.CHANNEL_BASELINE = False     # this ablation is about fixes 1-3 (subscriber outlier)
    ra.SNAPSHOTS = False            # one data pull per setting: no snapshot writes
    ra.english_word_share("warm up")            # load wordfreq once
    zipf = ra._zipf_frequency

    now = datetime.now(timezone.utc)
    date = now.strftime("%Y-%m-%d")
    out = {}
    for niche in load_niches(HERE / "niches.json", args.niches):
        queries = previous_queries(niche["name"], args.queries_from)
        profile = niche["profile"]
        for name, s in SETTINGS.items():
            ra.SUBSCRIBER_FLOOR = s["floor"]
            ra.CLUSTER_DISTANCE_THRESHOLD = s["dist"]
            ra._zipf_frequency = zipf if s["english"] else None
            print(f"\n=== {niche['name']} / {name} ===")
            r = ra.run_research(profile, profile.get("creator_niche", niche["name"]),
                                now=now, source="youtube", queries=queries)
            out[f"{niche['name']}|{name}"] = r

    (RESULTS / f"ablation_{date}.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    lines = [f"# V1 fixes ablation — {date}", "",
             f"Same data for every row (queries from {args.queries_from}). "
             "Types = trend / emerging / evergreen / topic over all clusters.", ""]
    for niche in dict.fromkeys(k.split("|")[0] for k in out):
        lines += [f"## {niche}", "",
                  "| Setting | Usable posts | Clusters | Types (T/E/Ev/Top) | Shown topics (type, creators, outlier) |",
                  "|---|---|---|---|---|"]
        for name in SETTINGS:
            r = out[f"{niche}|{name}"]
            st = r["stats"]
            types = "/".join(str(st.get("trend_types", {}).get(t, 0)) for t in ra.TYPE_RANK)
            shown = "; ".join(f"{t['topic']} ({t['trend_type']}, {t['channel_count']}, {t['median_outlier']:.1f})"
                              for t in r["trends"]) or "–"
            lines.append(f"| {name} | {st.get('posts_usable', '–')} | {st.get('clusters', '–')} | "
                         f"{types} | {shown.replace('|', '/')} |")
        lines.append("")
    md = RESULTS / f"ablation_{date}.md"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote {md}")


if __name__ == "__main__":
    main()
