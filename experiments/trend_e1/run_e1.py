"""
run_e1.py — Trend E1: YouTube (V1) vs Instagram (V2) as the research source.

Runs the same Research Agent (same queries, scoring, clustering and trend
definition) once per source for every niche in niches.json, then writes:

  results/<date>_<version>_<niche>.json   full run output (trends + stats)
  results/summary_<date>.md               side-by-side comparison
  results/labels_<date>.csv               one row per shown trend, for you to
                                          label as trend / not_trend by hand

After labelling:
  python experiments/trend_e1/run_e1.py --score experiments/trend_e1/results/labels_<date>.csv
prints precision per version (and per trend_type) and appends it to the summary.

Usage:
  python experiments/trend_e1/run_e1.py                       # both versions, all niches
  python experiments/trend_e1/run_e1.py --versions youtube    # V1 only
  python experiments/trend_e1/run_e1.py --niches motivation
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pipeline.agents import instagram_source as ig  # noqa: E402
from pipeline.agents import research_agent as ra  # noqa: E402

HERE = Path(__file__).parent
RESULTS = HERE / "results"
VERSION_NAMES = {"youtube": "V1 YouTube", "instagram": "V2 Instagram"}
LABELS = ("trend", "not_trend")


def load_niches(path: Path, only: list[str] | None) -> list[dict]:
    niches = json.loads(path.read_text(encoding="utf-8"))["niches"]
    for n in niches:
        if "profile_path" in n:
            n["profile"] = json.loads((ROOT / n["profile_path"]).read_text(encoding="utf-8"))
    return [n for n in niches if not only or n["name"] in only]


def previous_queries(niche: str, date: str) -> list[str] | None:
    """Queries of today's earlier YouTube run: same queries = fair re-runs + cache hits."""
    path = RESULTS / f"{date}_youtube_{niche}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8")).get("queries") or None
    return None


def run_one(version: str, niche: dict, now: datetime, top_k: int,
            queries: list[str] | None = None) -> dict:
    profile = niche["profile"]
    niche_text = profile.get("creator_niche", niche["name"])
    ig_config = None
    if version == "instagram":
        ig_config = {**ig.config_from_env(), "creators": niche.get("ig_creators", []),
                     "hashtags": niche.get("ig_hashtags", [])}
    started = time.perf_counter()
    result = ra.run_research(profile, niche_text, top_k=top_k, now=now,
                             source=version, ig_config=ig_config, queries=queries)
    result["seconds"] = round(time.perf_counter() - started, 1)
    result["niche"] = niche["name"]
    result["version"] = version
    return result


# ─── Summary ───────────────────────────────────────────────────────────────────

def _tick(ok: bool) -> str:
    return "✓" if ok else "✗"


def _fmt(x, nd=2):
    return "–" if x is None else f"{x:.{nd}f}"


def summary_markdown(runs: list[dict], date: str) -> str:
    out = [f"# Trend E1 — YouTube (V1) vs Instagram (V2) — {date}", "",
           "Same Research Agent for both; only the data source differs. "
           "Checks: **O**verperforms · **G**rowing · **S**preading · **R**ecent.", ""]
    for niche in dict.fromkeys(r["niche"] for r in runs):
        out += [f"## Niche: {niche}", "",
                "| | " + " | ".join(VERSION_NAMES[r["version"]] for r in runs if r["niche"] == niche) + " |",
                "|---|" + "---|" * sum(1 for r in runs if r["niche"] == niche)]
        nr = [r for r in runs if r["niche"] == niche]
        rows = {
            "Status": [("OK" if not r["error"] else f"✗ {r['error'][:90]}") for r in nr],
            "Usable posts": [str(r["stats"].get("posts_usable", "–")) for r in nr],
            "Distinct posts / clusters": [f"{r['stats'].get('posts_distinct', '–')} / "
                                          f"{r['stats'].get('clusters', '–')}" for r in nr],
            "All clusters by type (trend/emerging/evergreen/topic)": [
                "/".join(str(r["stats"].get("trend_types", {}).get(t, 0)) for t in ra.TYPE_RANK)
                if r["stats"].get("trend_types") else "–" for r in nr],
            "Niche recent share (sampling baseline)": [_fmt(r["stats"].get("niche_recent_share")) for r in nr],
            "Shown (top-k) high-confidence trends": [
                str(sum(1 for t in r["trends"] if t["trend_type"] == "trend")) for r in nr],
            "Mean creator_fit of shown": [
                _fmt(sum(t["creator_fit"] for t in r["trends"]) / len(r["trends"]))
                if r["trends"] else "–" for r in nr],
            "Cost": [r["stats"].get("api_cost", "–") for r in nr],
            "Time (s)": [str(r["seconds"]) for r in nr],
        }
        for name, vals in rows.items():
            out.append(f"| {name} | " + " | ".join(vals) + " |")
        out.append("")
        for r in nr:
            extra = []
            for key in ("failed_creators", "hashtags_skipped_weekly_limit", "failed_hashtags"):
                if r["stats"].get(key):
                    extra.append(f"{key}: {', '.join(r['stats'][key])}")
            if r["stats"].get("hashtag_access"):
                extra.append(f"Hashtag Search {r['stats']['hashtag_access']}")
            if r["version"] == "instagram" and "creators_ok" in r["stats"]:
                extra.append(f"Creators reached: {r['stats']['creators_ok']}, "
                             f"Reels from creators: {r['stats'].get('posts_from_creators', 0)}, "
                             f"from hashtags: {r['stats'].get('posts_from_hashtags', 0)}")
            out += [f"### {VERSION_NAMES[r['version']]}", ""]
            if extra:
                out += [f"- {e}" for e in extra] + [""]
            if not r["trends"]:
                out += ["_No trends._", ""]
                continue
            out += ["| # | Topic | Type | O G S R | Creators | Posts | Rel. growth | Outlier | Fit | Top evidence |",
                    "|---|---|---|---|---|---|---|---|---|---|"]
            for i, t in enumerate(r["trends"], 1):
                c = t["checks"]
                checks = " ".join(_tick(c[k]) for k in ("overperforms", "growing", "spreading", "recent"))
                ev = t["evidence"][0]
                topic = t["topic"].replace("|", "/")
                out.append(f"| {i} | {topic} | {t['trend_type']} | {checks} | {t['channel_count']} | "
                           f"{t['video_count']} | {_fmt(t['relative_growth'])} | {_fmt(t['median_outlier'])} | "
                           f"{_fmt(t['creator_fit'])} | [{ev['title'][:40].replace('|', '/')}]({ev['url']}) |")
            out.append("")
    return "\n".join(out)


def write_labels(runs: list[dict], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["version", "niche", "rank", "topic", "trend_type", "creators", "posts",
                    "evidence_urls", "label", "notes"])
        for r in runs:
            for i, t in enumerate(r["trends"], 1):
                w.writerow([r["version"], r["niche"], i, t["topic"], t["trend_type"],
                            t["channel_count"], t["video_count"],
                            " ".join(e["url"] for e in t["evidence"][:3]), "", ""])


# ─── Scoring hand labels ───────────────────────────────────────────────────────

def score_labels(path: Path) -> str:
    """Precision = share of shown trends a human agreed are real trends."""
    by_version: dict[str, list[str]] = defaultdict(list)
    by_type: dict[tuple[str, str], list[str]] = defaultdict(list)
    skipped = 0
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            label = row["label"].strip().lower()
            if label not in LABELS:
                skipped += 1
                continue
            by_version[row["version"]].append(label)
            by_type[(row["version"], row["trend_type"])].append(label)

    def precision(labels: list[str]) -> str:
        return f"{sum(lab == 'trend' for lab in labels) / len(labels):.2f} ({len(labels)} labelled)"

    out = [f"## Hand-label precision ({path.name})", "",
           "| Version | Precision@k (all shown) | " + " | ".join(ra.TYPE_RANK) + " |",
           "|---|---|" + "---|" * len(ra.TYPE_RANK)]
    for version, labels in by_version.items():
        cells = [precision(by_type[(version, t)]) if by_type[(version, t)] else "–"
                 for t in ra.TYPE_RANK]
        out.append(f"| {VERSION_NAMES.get(version, version)} | {precision(labels)} | " + " | ".join(cells) + " |")
    if skipped:
        out += ["", f"_{skipped} rows had no label and were skipped._"]
    return "\n".join(out)


# ─── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--versions", nargs="+", default=["youtube", "instagram"], choices=list(VERSION_NAMES))
    parser.add_argument("--niches", nargs="+", default=None)
    parser.add_argument("--config", type=Path, default=HERE / "niches.json")
    parser.add_argument("--top-k", type=int, default=ra.TOP_K_TRENDS)
    parser.add_argument("--score", type=Path, default=None, help="labels CSV to score instead of running")
    parser.add_argument("--new-queries", action="store_true",
                        help="ask the LLM for fresh queries instead of reusing today's")
    args = parser.parse_args()

    if args.score:
        text = score_labels(args.score)
        print(text)
        date = re.search(r"\d{4}-\d{2}-\d{2}", args.score.name)
        summary = RESULTS / f"summary_{date.group(0) if date else 'latest'}.md"
        if summary.exists():
            summary.write_text(summary.read_text(encoding="utf-8") + "\n\n" + text + "\n", encoding="utf-8")
            print(f"\nAppended to {summary}")
        return

    now = datetime.now(timezone.utc)
    date = now.strftime("%Y-%m-%d")
    RESULTS.mkdir(parents=True, exist_ok=True)
    runs = []
    for niche in load_niches(args.config, args.niches):
        # both versions share one query set per niche
        queries = None if args.new_queries else previous_queries(niche["name"], date)
        for version in args.versions:
            print(f"\n{'=' * 70}\n{VERSION_NAMES[version]} — {niche['name']}\n{'=' * 70}")
            result = run_one(version, niche, now, args.top_k, queries)
            queries = queries or result["queries"]
            runs.append(result)
            (RESULTS / f"{date}_{version}_{niche['name']}.json").write_text(
                json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    summary = RESULTS / f"summary_{date}.md"
    summary.write_text(summary_markdown(runs, date) + "\n", encoding="utf-8")
    write_labels(runs, RESULTS / f"labels_{date}.csv")
    print(f"\nSummary: {summary}\nLabels:  {RESULTS / f'labels_{date}.csv'}")


if __name__ == "__main__":
    main()
