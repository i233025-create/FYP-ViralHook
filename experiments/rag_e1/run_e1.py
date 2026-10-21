"""
run_e1.py — E1: which search method best finds a creator's own past reels? (step 2)
====================================================================================
For each creator separately (the system only ever searches one creator's
own library):

  query    = reel i's cleaned caption
  docs     = transcripts of all of that creator's reels (no captions inside)
  correct  = reel i's own transcript

Every method ranks the transcripts for every caption, and we record where
the correct one lands. Run prepare_data.py first.

Outputs:
  results/e1_results.json   config, dataset stats, metrics, every query's rank
  results/e1_summary.md     tables ready for the report

Usage:
  python run_e1.py                       # all methods
  python run_e1.py --quick               # 6 representative methods (faster)
  python run_e1.py --methods bm25 minilm bm25+minilm
"""

from __future__ import annotations

import argparse
import json
import platform
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from metrics import KS, bootstrap_ci, correct_ranks, random_baseline, summarize
from prepare_data import CAPTIONS_FILE, DATA_DIR, TRANSCRIPTS_FILE, read_captions
from retrievers import DEFAULT_METHODS, QUICK_METHODS, is_multilingual, make_retriever
from text_clean import MIN_QUERY_WORDS, clean_caption, dominant_script, word_count

HERE = Path(__file__).parent
RESULTS_DIR = HERE / "results"
MIN_TRANSCRIPT_WORDS = 10   # below this the reel is mostly music / no speech
MIN_REELS = 5               # a creator with fewer usable reels is skipped
RECOMMENDED_REELS = 15
METRIC_COLS = [f"R@{k}" for k in KS] + ["MRR"]


# ─── Dataset ───────────────────────────────────────────────────────────────────

def load_creator(creator_dir: Path, transcripts_name: str = TRANSCRIPTS_FILE) -> tuple[list[dict], dict]:
    """Usable (query, doc) pairs for one creator, plus why the rest were excluded."""
    transcripts_path = creator_dir / transcripts_name
    transcripts = json.loads(transcripts_path.read_text(encoding="utf-8")) if transcripts_path.exists() else {}

    items, excluded, seen_queries = [], {}, set()

    def exclude(reason: str):
        excluded[reason] = excluded.get(reason, 0) + 1

    for row in read_captions(creator_dir):
        transcript = (transcripts.get(row["file"]) or {}).get("text", "")
        query = clean_caption(row["caption"])
        if row["file"] not in transcripts:
            exclude("not transcribed")
        elif not transcript:
            exclude("no speech")
        elif word_count(transcript) < MIN_TRANSCRIPT_WORDS:
            exclude(f"transcript < {MIN_TRANSCRIPT_WORDS} words")
        elif word_count(query) < MIN_QUERY_WORDS:
            exclude(f"caption < {MIN_QUERY_WORDS} words after cleaning")
        elif query.lower() in seen_queries:
            exclude("duplicate caption")
        else:
            seen_queries.add(query.lower())
            items.append({"file": row["file"], "raw_caption": row["caption"], "query": query, "doc": transcript})

    stats = {
        "reels_listed": sum(excluded.values()) + len(items),
        "reels_used": len(items),
        "excluded": excluded,
        "avg_query_words": round(float(np.mean([word_count(i["query"]) for i in items])), 1) if items else 0,
        "avg_transcript_words": round(float(np.mean([word_count(i["doc"]) for i in items])), 1) if items else 0,
        "query_script": _script_mix([i["query"] for i in items]),
        "transcript_script": _script_mix([i["doc"] for i in items]),
    }
    return items, stats


def _script_mix(texts: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for t in texts:
        script = dominant_script(t)
        counts[script] = counts.get(script, 0) + 1
    return counts


def load_dataset(creator_names: list[str] | None,
                 transcripts_name: str = TRANSCRIPTS_FILE) -> tuple[dict[str, list[dict]], dict[str, dict]]:
    if not DATA_DIR.exists():
        raise SystemExit(f"No data folder at {DATA_DIR} — see README.md")
    dirs = sorted(d for d in DATA_DIR.iterdir() if (d / CAPTIONS_FILE).exists())
    if creator_names:
        dirs = [d for d in dirs if d.name in creator_names]

    dataset, stats = {}, {}
    for d in dirs:
        items, s = load_creator(d, transcripts_name)
        stats[d.name] = s
        s["skipped"] = len(items) < MIN_REELS
        if s["skipped"]:
            print(f"[E1] SKIP {d.name}: only {len(items)} usable reels (need {MIN_REELS}+). Excluded: {s['excluded']}")
            continue
        if len(items) < RECOMMENDED_REELS:
            print(f"[E1] WARNING {d.name}: {len(items)} usable reels — {RECOMMENDED_REELS}+ recommended")
        dataset[d.name] = items
    if not dataset:
        raise SystemExit("No creator has enough usable reels. Run prepare_data.py and check captions.csv.")
    return dataset, stats


# ─── Evaluation ────────────────────────────────────────────────────────────────

def evaluate_method(name: str, dataset: dict[str, list[dict]]) -> dict:
    retriever = make_retriever(name)
    per_creator, all_ranks, queries_out = {}, [], []
    index_s = query_s = 0.0
    n_queries = 0

    for creator, items in dataset.items():
        started = time.perf_counter()
        retriever.index([i["doc"] for i in items])
        index_s += time.perf_counter() - started

        started = time.perf_counter()
        scores = retriever.score([i["query"] for i in items])
        query_s += time.perf_counter() - started
        n_queries += len(items)

        ranks = correct_ranks(scores)
        all_ranks.extend(ranks.tolist())
        per_creator[creator] = summarize(ranks)
        top1 = np.argmax(scores, axis=1)
        for i, item in enumerate(items):
            queries_out.append({"creator": creator, "file": item["file"], "query": item["query"],
                                "rank": int(ranks[i]), "top1_file": items[top1[i]]["file"]})

    all_ranks = np.array(all_ranks)
    macro = {m: float(np.mean([per_creator[c][m] for c in per_creator])) for m in METRIC_COLS}
    return {
        "method": name,
        "family": retriever.family,
        "multilingual": is_multilingual(name),
        "params_m": retriever.params_m,
        "macro": macro,
        "pooled": summarize(all_ranks),
        "ci95": {m: bootstrap_ci(all_ranks, m) for m in ("R@3", "MRR")},
        "per_creator": per_creator,
        "index_time_s": round(index_s, 2),
        "query_ms": round(1000 * query_s / n_queries, 1),
        "queries": queries_out,
    }


# ─── Reporting ─────────────────────────────────────────────────────────────────

def _pct(x: float) -> str:
    return f"{100 * x:.1f}"


def summary_markdown(results: list[dict], baseline: dict, stats: dict, dataset: dict, config: dict) -> str:
    ok = sorted((r for r in results if "error" not in r), key=lambda r: -r["macro"]["MRR"])
    creators = list(dataset)
    lines = [
        "# E1 — Caption → transcript retrieval",
        "",
        f"Run: {config['timestamp']} · device: {config['device']} · "
        f"{len(creators)} creators, {sum(len(v) for v in dataset.values())} queries",
        "",
        "## Dataset",
        "",
        "| Creator | Reels used / listed | Avg caption words | Avg transcript words | Caption script | Transcript script | Excluded |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, s in stats.items():
        label = f"{name} (skipped: < {MIN_REELS} usable reels)" if s.get("skipped") else name
        lines.append(f"| {label} | {s['reels_used']} / {s['reels_listed']} | {s['avg_query_words']} | "
                     f"{s['avg_transcript_words']} | {s['query_script']} | {s['transcript_script']} | "
                     f"{s['excluded'] or '—'} |")

    lines += [
        "",
        "## Overall (macro average over creators, %)",
        "",
        "95% CI from bootstrap over all queries. Ranked by MRR.",
        "",
        "| Method | Family | Multilingual | Params (M) | R@1 | R@3 | R@5 | MRR | R@3 95% CI | Query ms |",
        "|---|---|---|---|---|---|---|---|---|---|",
        f"| *random* | — | — | — | {_pct(baseline['R@1'])} | {_pct(baseline['R@3'])} | "
        f"{_pct(baseline['R@5'])} | {_pct(baseline['MRR'])} | — | — |",
    ]
    for r in ok:
        m, ci = r["macro"], r["ci95"]["R@3"]
        lines.append(f"| {r['method']} | {r['family']} | {'yes' if r['multilingual'] else 'no'} | "
                     f"{r['params_m'] or '—'} | {_pct(m['R@1'])} | {_pct(m['R@3'])} | {_pct(m['R@5'])} | "
                     f"{_pct(m['MRR'])} | {_pct(ci[0])}–{_pct(ci[1])} | {r['query_ms']} |")

    lines += ["", "## R@3 per creator (%)", "",
              "| Method | " + " | ".join(creators) + " |",
              "|---|" + "---|" * len(creators)]
    for r in ok:
        lines.append(f"| {r['method']} | " + " | ".join(_pct(r["per_creator"][c]["R@3"]) for c in creators) + " |")

    failed = [r for r in results if "error" in r]
    if failed:
        lines += ["", "## Methods that failed to run", ""]
        lines += [f"- {r['method']}: {r['error']}" for r in failed]
    return "\n".join(lines) + "\n"


def print_table(results: list[dict], baseline: dict) -> None:
    print("\n" + "=" * 78)
    print(f"  {'method':<22}{'R@1':>8}{'R@3':>8}{'R@5':>8}{'MRR':>8}   {'R@3 95% CI':<14}{'ms/q':>7}")
    print("  " + "-" * 76)
    print(f"  {'random':<22}" + "".join(f"{_pct(baseline[m]):>8}" for m in METRIC_COLS))
    for r in sorted(results, key=lambda r: -r["macro"]["MRR"] if "error" not in r else 1):
        if "error" in r:
            print(f"  {r['method']:<22}  FAILED: {r['error'][:50]}")
            continue
        ci = r["ci95"]["R@3"]
        print(f"  {r['method']:<22}" + "".join(f"{_pct(r['macro'][m]):>8}" for m in METRIC_COLS)
              + f"   {_pct(ci[0]):>5}–{_pct(ci[1]):<7}{r['query_ms']:>7}")
    print("=" * 78)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--methods", nargs="*", help="methods to run (default: all)")
    parser.add_argument("--quick", action="store_true", help=f"only {', '.join(QUICK_METHODS)}")
    parser.add_argument("--creators", nargs="*", help="creator folder names (default: all)")
    parser.add_argument("--tag", default="", help="suffix for output files, e.g. 'whisper-medium'")
    parser.add_argument("--transcripts", default=TRANSCRIPTS_FILE,
                        help="transcripts file in each creator folder (see prepare_data.py --out)")
    args = parser.parse_args()

    methods = args.methods or (QUICK_METHODS if args.quick else DEFAULT_METHODS)
    dataset, stats = load_dataset(args.creators, args.transcripts)
    baseline = {m: float(np.mean([random_baseline(len(v))[m] for v in dataset.values()])) for m in METRIC_COLS}

    import torch
    config = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "device": "cuda" if torch.cuda.is_available() else "cpu",
        "python": platform.python_version(),
        "methods": methods,
        "transcripts": args.transcripts,
        "min_query_words": MIN_QUERY_WORDS,
        "min_transcript_words": MIN_TRANSCRIPT_WORDS,
    }
    print(f"[E1] {len(dataset)} creators: " + ", ".join(f"{k} ({len(v)})" for k, v in dataset.items()))

    results = []
    for name in methods:
        print(f"[E1] {name} ...", flush=True)
        try:
            results.append(evaluate_method(name, dataset))
        except Exception as exc:   # e.g. model download failed — keep the other methods
            print(f"[E1] {name} FAILED: {exc}")
            results.append({"method": name, "error": f"{type(exc).__name__}: {exc}"})

    print_table(results, baseline)

    RESULTS_DIR.mkdir(exist_ok=True)
    suffix = f"_{args.tag}" if args.tag else ""
    json_path = RESULTS_DIR / f"e1_results{suffix}.json"
    md_path = RESULTS_DIR / f"e1_summary{suffix}.md"
    json_path.write_text(json.dumps({"config": config, "dataset": stats, "random_baseline": baseline,
                                     "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(summary_markdown(results, baseline, stats, dataset, config), encoding="utf-8")
    print(f"[E1] Saved {json_path.relative_to(HERE)} and {md_path.relative_to(HERE)}")


if __name__ == "__main__":
    main()
