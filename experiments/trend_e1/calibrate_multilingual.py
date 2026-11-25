"""
calibrate_multilingual.py — thresholds for the multilingual embedding model.

The English model's thresholds (cluster distance 0.5, creator_fit ≥ 0.45)
were tuned on E1 data. The multilingual model spreads cosines differently,
so the same numbers would make clusters tighter or looser. This script
embeds the SAME English titles with both models and picks, for the
multilingual one:
  - the cluster distance whose cluster count is closest to the English
    model's at CLUSTER_DISTANCE_THRESHOLD, and
  - the creator-fit threshold that keeps the same share of clusters as
    MIN_CREATOR_FIT does for the English model.

Uses today's cached searches (run run_e1.py first); ~10 quota units per niche
for video details.

Usage:
  python experiments/trend_e1/calibrate_multilingual.py
Writes results/calibration_multilingual_<date>.md.
"""
from __future__ import annotations

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

DISTANCES = [round(x, 2) for x in np.arange(0.30, 0.71, 0.02)]


def fits(embeddings: np.ndarray, clusters: list[list[int]], topics: np.ndarray) -> list[float]:
    out = []
    for g in clusters:
        if len(g) < ra.MIN_WEAK_CLUSTER_SIZE:
            continue
        c = embeddings[g].mean(axis=0)
        c = c / (np.linalg.norm(c) or 1.0)
        out.append(float(max(0.0, (topics @ c).max())))
    return out


def main() -> None:
    ra.CHANNEL_BASELINE = False
    ra.SNAPSHOTS = False
    now = datetime.now(timezone.utc)
    api_key = os.getenv("YOUTUBE_API_KEY", "")
    rows = []
    for niche in load_niches(HERE / "niches.json", None):
        videos = ra.collect_videos(niche["queries"], api_key, now)          # English only
        texts = [ra.video_text(v) for v in videos]
        profile = niche["profile"]
        en = ra._embed(texts, False)
        ml = ra._embed(texts, True)
        en_topics = ra._profile_embedding(profile, niche["name"], False)
        ml_topics = ra._profile_embedding(profile, niche["name"], True)

        en_clusters = ra.cluster_embeddings(en, ra.CLUSTER_DISTANCE_THRESHOLD)
        target = len(en_clusters)
        counts = {d: len(ra.cluster_embeddings(ml, d)) for d in DISTANCES}
        best_d = min(DISTANCES, key=lambda d: (abs(counts[d] - target), d))

        en_fits = fits(en, en_clusters, en_topics)
        keep_share = np.mean([f >= ra.MIN_CREATOR_FIT for f in en_fits]) if en_fits else 0.0
        ml_fits = sorted(fits(ml, ra.cluster_embeddings(ml, best_d), ml_topics), reverse=True)
        k = max(int(round(keep_share * len(ml_fits))), 1)
        best_fit = round(ml_fits[k - 1], 3) if ml_fits else ra.MIN_CREATOR_FIT
        rows.append((niche["name"], len(videos), target, float(best_d), counts[best_d],
                     round(float(keep_share), 2), best_fit))
        print(rows[-1])

    date = now.strftime("%Y-%m-%d")
    d_med = float(np.median([r[3] for r in rows]))
    f_med = float(np.median([r[6] for r in rows]))
    lines = [f"# Multilingual model calibration — {date}", "",
             f"Same English titles, both models. English model: distance "
             f"{ra.CLUSTER_DISTANCE_THRESHOLD}, creator_fit ≥ {ra.MIN_CREATOR_FIT}.", "",
             "| Niche | Titles | English clusters | Multilingual distance with closest count | its clusters "
             "| Share of clusters kept by English fit gate | Multilingual fit keeping that share |",
             "|---|---|---|---|---|---|---|"]
    lines += [f"| {' | '.join(str(x) for x in r)} |" for r in rows]
    lines += ["", f"**Median: distance {d_med:.2f}, creator_fit {f_med:.3f}.**"]
    out = RESULTS / f"calibration_multilingual_{date}.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
