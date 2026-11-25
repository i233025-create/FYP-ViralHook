"""
forward_check.py — are the topics shown on day A still there (or bigger) on day B?

For every topic shown in results/<A>_youtube_<niche>.json, the centroid of
its evidence titles is compared with every usable video pulled today with
the same queries (searches come from the 6-hour cache after a run_e1.py run
on the same day, so this costs ~15 quota units). A video "matches" when its
cosine similarity to the centroid is >= MATCH_SIMILARITY.

Usage:
  python experiments/trend_e1/forward_check.py --from 2026-11-18
Writes results/forward_<A>_to_<today>.md.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))

from pipeline.agents import research_agent as ra  # noqa: E402
from run_e1 import RESULTS, load_niches  # noqa: E402

MATCH_SIMILARITY = 0.6


def _unit(x: np.ndarray) -> np.ndarray:
    return x / np.clip(np.linalg.norm(x, axis=-1, keepdims=True), 1e-9, None)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--from", dest="day_a", required=True, metavar="YYYY-MM-DD")
    p.add_argument("--niches", nargs="+", default=None)
    args = p.parse_args()

    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    api_key = os.getenv("YOUTUBE_API_KEY", "")
    lines = [f"# Forward check — topics shown on {args.day_a}, looked up on {today}", "",
             f"Same queries both days. A video matches a topic when its title embedding has "
             f"cosine ≥ {MATCH_SIMILARITY} with the centroid of the topic's {args.day_a} evidence.", ""]

    for niche in load_niches(HERE / "niches.json", args.niches):
        old = json.loads((RESULTS / f"{args.day_a}_youtube_{niche['name']}.json").read_text(encoding="utf-8"))
        videos = ra.collect_videos(old["queries"], api_key, now)
        emb = _unit(np.asarray(ra.embed_texts([ra.video_text(v) for v in videos])))
        lines += [f"## {niche['name']} ({len(videos)} usable videos on {today})", "",
                  f"| Topic ({args.day_a}) | Type then | Creators / posts then | "
                  f"Matching creators / posts now | of which uploaded last 3 days | Still there? |",
                  "|---|---|---|---|---|---|"]
        for t in old["trends"]:
            ev = [{"title": e.get("title", ""), "description": "", "tags": []} for e in t["evidence"]]
            centroid = _unit(np.asarray(ra.embed_texts([ra.video_text(e) for e in ev])).mean(axis=0))
            sims = emb @ centroid
            hits = [v for v, s in zip(videos, sims) if s >= MATCH_SIMILARITY]
            channels = {v["channel_id"] for v in hits}
            recent = sum(ra._hours_since(v["published_at"], now) <= 72 for v in hits)
            then_c = t["channel_count"]
            verdict = ("grew" if len(channels) > then_c else
                       "about the same" if len(channels) >= max(2, then_c - 1) else
                       "faded" if channels else "gone")
            lines.append(f"| {t['topic']} | {t['trend_type']} | {then_c} / {t['video_count']} | "
                         f"{len(channels)} / {len(hits)} | {recent} | {verdict} |")
        lines.append("")

    out = RESULTS / f"forward_{args.day_a}_to_{today}.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
