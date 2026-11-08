"""
run_e1.py — E1: which search method best finds a creator's own past reels? (step 2)
====================================================================================
For each creator separately (the system only ever searches one creator's
own library):

  query    = reel i's cleaned caption (--queries caption)
             or a hand-written topic for reel i (--queries topic, topics.csv)
  docs     = transcripts of that creator's reels (no captions inside);
             by default ALL transcribed reels, so reels without a usable
             query still compete as distractors (--library queryable = v1)
  correct  = reel i's own transcript

Every method ranks the transcripts for every query, and we record where
the correct one lands. Run prepare_data.py first.

Outputs:
  results/e1_results.json   config, dataset stats, metrics, every query's rank
  results/e1_summary.md     tables ready for the report

Usage:
  python run_e1.py                       # all methods
  python run_e1.py --quick               # 6 representative methods (faster)
  python run_e1.py --methods bm25 minilm bm25+minilm
  python run_e1.py --creators "Rabika Tahir v2" --queries topic --tag v2_topic
"""

from __future__ import annotations

import argparse
import csv
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
TOPICS_FILE = "topics.csv"  # hand-written topic queries, see make_topic_sheet.py
MIN_TRANSCRIPT_WORDS = 10   # below this the reel is mostly music / no speech
MIN_REELS = 5               # a creator with fewer usable reels is skipped
RECOMMENDED_REELS = 15
METRIC_COLS = [f"R@{k}" for k in KS] + ["MRR"]


# ─── Dataset ───────────────────────────────────────────────────────────────────

def read_topics(creator_dir: Path) -> dict[str, str]:
    """topics.csv (file,topic,...) → {file: topic}; extra columns are ignored."""
    path = creator_dir / TOPICS_FILE
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {r["file"].strip(): (r.get("topic") or "").strip() for r in csv.DictReader(f) if r.get("file")}


def load_creator(creator_dir: Path, transcripts_name: str = TRANSCRIPTS_FILE,
                 query_source: str = "caption", library_mode: str = "all") -> tuple[dict, dict]:
    """
    One creator's search library and queries.

      library  every reel with a usable transcript (the docs searched)
      queries  the library reels that also have a usable query; each points at
               its own transcript via `target` (index into library)

    library_mode="queryable" keeps only reels that have a query (the E1 v1
    setup); "all" keeps the rest as distractors, which is closer to a real
    creator's library and makes the task harder.
    """
    transcripts_path = creator_dir / transcripts_name
    transcripts = json.loads(transcripts_path.read_text(encoding="utf-8")) if transcripts_path.exists() else {}
    topics = read_topics(creator_dir) if query_source == "topic" else {}

    library, candidates = [], []
    not_in_library, not_query, seen_queries = {}, {}, set()

    def count(bucket: dict, reason: str):
        bucket[reason] = bucket.get(reason, 0) + 1

    rows = read_captions(creator_dir)
    for row in rows:
        transcript = (transcripts.get(row["file"]) or {}).get("text", "")
        if row["file"] not in transcripts:
            count(not_in_library, "not transcribed")
            continue
        if not transcript:
            count(not_in_library, "no speech")
            continue
        if word_count(transcript) < MIN_TRANSCRIPT_WORDS:
            count(not_in_library, f"transcript < {MIN_TRANSCRIPT_WORDS} words")
            continue
        library.append({"file": row["file"], "doc": transcript})

        if query_source == "topic":
            query = topics.get(row["file"], "")
            short_reason = "no topic written" if not query else f"topic < {MIN_QUERY_WORDS} words"
        else:
            query = clean_caption(row["caption"])
            short_reason = f"caption < {MIN_QUERY_WORDS} words after cleaning"
        if word_count(query) < MIN_QUERY_WORDS:
            count(not_query, short_reason)
        elif query.lower() in seen_queries:
            count(not_query, f"duplicate {query_source}")
        else:
            seen_queries.add(query.lower())
            candidates.append({"file": row["file"], "raw_caption": row["caption"], "query": query})

    if library_mode == "queryable":
        keep = {c["file"] for c in candidates}
        library = [d for d in library if d["file"] in keep]
    position = {d["file"]: i for i, d in enumerate(library)}
    queries = [{**c, "target": position[c["file"]]} for c in candidates]

    stats = {
        "reels_listed": len(rows),
        "library_size": len(library),
        "queries": len(queries),
        "not_in_library": not_in_library,
        "not_query": not_query,
        "avg_query_words": round(float(np.mean([word_count(q["query"]) for q in queries])), 1) if queries else 0,
        "avg_transcript_words": round(float(np.mean([word_count(d["doc"]) for d in library])), 1) if library else 0,
        "query_script": _script_mix([q["query"] for q in queries]),
        "transcript_script": _script_mix([d["doc"] for d in library]),
    }
    return {"library": library, "queries": queries}, stats


def _script_mix(texts: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for t in texts:
        script = dominant_script(t)
        counts[script] = counts.get(script, 0) + 1
    return counts


def load_dataset(creator_names: list[str] | None, transcripts_name: str = TRANSCRIPTS_FILE,
                 query_source: str = "caption", library_mode: str = "all") -> tuple[dict[str, dict], dict[str, dict]]:
    if not DATA_DIR.exists():
        raise SystemExit(f"No data folder at {DATA_DIR} — see README.md")
    dirs = sorted(d for d in DATA_DIR.iterdir() if (d / CAPTIONS_FILE).exists())
    if creator_names:
        dirs = [d for d in dirs if d.name in creator_names]

    dataset, stats = {}, {}
    for d in dirs:
        data, s = load_creator(d, transcripts_name, query_source, library_mode)
        stats[d.name] = s
        n = len(data["queries"])
        s["skipped"] = n < MIN_REELS
        if s["skipped"]:
            print(f"[E1] SKIP {d.name}: only {n} usable queries (need {MIN_REELS}+). "
                  f"Not in library: {s['not_in_library']}; no query: {s['not_query']}")
            continue
        if n < RECOMMENDED_REELS:
            print(f"[E1] WARNING {d.name}: {n} usable queries — {RECOMMENDED_REELS}+ recommended")
        dataset[d.name] = data
    if not dataset:
        raise SystemExit("No creator has enough usable reels. Run prepare_data.py and check captions.csv.")
    return dataset, stats


# ─── Evaluation ────────────────────────────────────────────────────────────────

def evaluate_method(name: str, dataset: dict[str, dict]) -> dict:
    retriever = make_retriever(name)
    per_creator, all_ranks, queries_out = {}, [], []
    index_s = query_s = 0.0
    n_queries = 0

    for creator, data in dataset.items():
        library, queries = data["library"], data["queries"]
        started = time.perf_counter()
        retriever.index([d["doc"] for d in library])
        index_s += time.perf_counter() - started

        started = time.perf_counter()
        scores = retriever.score([q["query"] for q in queries])
        query_s += time.perf_counter() - started
        n_queries += len(queries)

        ranks = correct_ranks(scores, [q["target"] for q in queries])
        all_ranks.extend(ranks.tolist())
        per_creator[creator] = summarize(ranks)
        top1 = np.argmax(scores, axis=1)
        for i, q in enumerate(queries):
            queries_out.append({"creator": creator, "file": q["file"], "query": q["query"],
                                "rank": int(ranks[i]), "top1_file": library[top1[i]]["file"]})

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
        f"# E1 — {config['query_source'].capitalize()} → transcript retrieval",
        "",
        f"Run: {config['timestamp']} · device: {config['device']} · "
        f"{len(creators)} creators, {sum(len(v['queries']) for v in dataset.values())} queries · "
        f"queries: {config['query_source']} · library: {config['library_mode']}",
        "",
        "## Dataset",
        "",
        "| Creator | Reels listed | Library (docs) | Queries | Avg query words | Avg transcript words "
        "| Query script | Transcript script | Not in library | No usable query |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name, s in stats.items():
        label = f"{name} (skipped: < {MIN_REELS} queries)" if s.get("skipped") else name
        lines.append(f"| {label} | {s['reels_listed']} | {s['library_size']} | {s['queries']} | "
                     f"{s['avg_query_words']} | {s['avg_transcript_words']} | {s['query_script']} | "
                     f"{s['transcript_script']} | {s['not_in_library'] or '—'} | {s['not_query'] or '—'} |")

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
    parser.add_argument("--queries", dest="query_source", choices=["caption", "topic"], default="caption",
                        help="caption: cleaned Instagram caption; topic: hand-written topics.csv "
                             "(see make_topic_sheet.py)")
    parser.add_argument("--library", dest="library_mode", choices=["all", "queryable"], default="all",
                        help="all: every transcribed reel is searched (reels without a query are "
                             "distractors); queryable: only reels that have a query (E1 v1 setup)")
    args = parser.parse_args()

    methods = args.methods or (QUICK_METHODS if args.quick else DEFAULT_METHODS)
    dataset, stats = load_dataset(args.creators, args.transcripts, args.query_source, args.library_mode)
    baseline = {m: float(np.mean([random_baseline(len(v["library"]))[m] for v in dataset.values()]))
                for m in METRIC_COLS}

    import torch
    config = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "device": "cuda" if torch.cuda.is_available() else "cpu",
        "python": platform.python_version(),
        "methods": methods,
        "transcripts": args.transcripts,
        "query_source": args.query_source,
        "library_mode": args.library_mode,
        "min_query_words": MIN_QUERY_WORDS,
        "min_transcript_words": MIN_TRANSCRIPT_WORDS,
    }
    print(f"[E1] {len(dataset)} creators: " + ", ".join(
        f"{k} ({len(v['queries'])} queries / {len(v['library'])} docs)" for k, v in dataset.items()))

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
