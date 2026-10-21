"""
run_e3.py — E3: can the system pick the creator's right photo for each scene?
==============================================================================
For each asset library (e.g. FAST admissions):

  queries  = scene descriptions, as a script would write them
  assets   = the creator's photos + distractor photos
  answer   = the photo(s) you marked as fitting each scene (or none)

Every method ranks all photos for every scene. We record where the first
correct photo lands, how often a distractor wins, and whether the best
photo's score can tell "a photo fits" from "nothing fits".

Layout (see README.md):
  data/<library>/assets/        the creator's photos
  data/<library>/distractors/   other photos (other campuses, random images)
  data/<library>/queries.csv    query,relevant_files,category

Usage:
  python run_e3.py --quick
  python run_e3.py
  python run_e3.py --methods clip-b32 siglip-base
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

from metrics import (KS, auc, best_threshold, bootstrap_ci, distractor_rate, first_relevant_ranks,
                     random_baseline, summarize)
from visual_models import DEFAULT_METHODS, QUICK_METHODS, make_retriever

HERE = Path(__file__).parent
DATA_DIR = HERE / "data"
RESULTS_DIR = HERE / "results"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
MAX_SIDE = 1024   # phone photos are huge; every model resizes to <= 384 px anyway
METRIC_COLS = [f"R@{k}" for k in KS] + ["MRR"]


# ─── Dataset ───────────────────────────────────────────────────────────────────

def load_images(folder: Path) -> tuple[list, list[Path]]:
    from PIL import Image, ImageOps
    images, paths = [], []
    if not folder.exists():
        return images, paths
    for path in sorted(folder.iterdir()):
        if path.suffix.lower() not in IMAGE_EXTS:
            if path.is_file():
                print(f"[E3] skip {path.name}: not a supported image ({', '.join(sorted(IMAGE_EXTS))}) — "
                      f"convert HEIC photos to JPG")
            continue
        try:
            img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
        except Exception as exc:
            print(f"[E3] skip {path.name}: cannot open ({exc})")
            continue
        img.thumbnail((MAX_SIDE, MAX_SIDE))
        images.append(img)
        paths.append(path)
    return images, paths


def read_queries(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    missing = {"query", "relevant_files"} - set(rows[0].keys() if rows else [])
    if missing:
        raise SystemExit(f"{path}: missing column(s) {sorted(missing)} — expected 'query,relevant_files,category'")
    out = []
    for r in rows:
        if not (r.get("query") or "").strip():
            continue
        files = [f.strip() for f in (r.get("relevant_files") or "").split(";") if f.strip()]
        out.append({"query": r["query"].strip(), "relevant_files": files,
                    "category": (r.get("category") or "").strip() or ("no_match" if not files else "other")})
    return out


def load_library(lib_dir: Path) -> dict:
    asset_imgs, asset_paths = load_images(lib_dir / "assets")
    dist_imgs, dist_paths = load_images(lib_dir / "distractors")
    if not asset_paths:
        raise SystemExit(f"{lib_dir.name}: no photos in {lib_dir / 'assets'}")

    names = [p.name for p in asset_paths]
    index_of = {n: i for i, n in enumerate(names)}
    queries = read_queries(lib_dir / "queries.csv")

    unknown = sorted({f for q in queries for f in q["relevant_files"] if f not in index_of})
    if unknown:
        raise SystemExit(f"{lib_dir.name}: queries.csv names photos not in assets/: {unknown}")
    if not any(q["relevant_files"] for q in queries):
        raise SystemExit(f"{lib_dir.name}: no scene has relevant_files filled in — label queries.csv first "
                         f"(see README.md, step 2)")

    return {
        "name": lib_dir.name,
        "images": asset_imgs + dist_imgs,
        "paths": asset_paths + dist_paths,
        "is_distractor": np.array([False] * len(asset_paths) + [True] * len(dist_paths)),
        "queries": queries,
        "relevant": [{index_of[f] for f in q["relevant_files"]} for q in queries],
    }


def library_stats(lib: dict) -> dict:
    with_match = sum(1 for r in lib["relevant"] if r)
    categories: dict[str, int] = {}
    for q in lib["queries"]:
        categories[q["category"]] = categories.get(q["category"], 0) + 1
    return {
        "creator_photos": int((~lib["is_distractor"]).sum()),
        "distractors": int(lib["is_distractor"].sum()),
        "scenes_with_match": with_match,
        "scenes_no_match": len(lib["queries"]) - with_match,
        "categories": categories,
    }


# ─── Evaluation ────────────────────────────────────────────────────────────────

def evaluate_method(name: str, libraries: list[dict]) -> dict:
    retriever = make_retriever(name)
    per_library, all_ranks, queries_out = {}, [], []
    index_s = query_s = 0.0
    n_images = n_queries = 0

    for lib in libraries:
        started = time.perf_counter()
        retriever.index(lib["images"], lib["paths"])
        index_s += time.perf_counter() - started
        n_images += len(lib["images"])

        started = time.perf_counter()
        scores = retriever.score([q["query"] for q in lib["queries"]])
        query_s += time.perf_counter() - started
        n_queries += len(lib["queries"])

        relevant = lib["relevant"]
        ranks = first_relevant_ranks(scores, relevant)
        all_ranks.extend(ranks.tolist())
        result = summarize(ranks)
        result["distractor_top1"] = distractor_rate(scores, relevant, lib["is_distractor"])

        # Per-category Recall@3 (scenes with a match only)
        by_cat: dict[str, list[int]] = {}
        match_queries = [q for q, rel in zip(lib["queries"], relevant) if rel]
        for q, r in zip(match_queries, ranks):
            by_cat.setdefault(q["category"], []).append(int(r))
        result["category_R@3"] = {c: float(np.mean(np.array(r) <= 3)) for c, r in by_cat.items()}

        # Fallback decision: best photo's score for scenes with vs without a fitting photo
        best = scores.max(axis=1)
        has_match = np.array([bool(r) for r in relevant])
        if retriever.thresholdable and has_match.any() and (~has_match).any():
            pos, neg = best[has_match], best[~has_match]
            result["no_match_auc"] = auc(pos, neg)
            result["threshold"] = best_threshold(pos, neg)
        per_library[lib["name"]] = result

        rank_iter = iter(ranks.tolist())
        for q_i, q in enumerate(lib["queries"]):
            top = np.argsort(-scores[q_i])[:3]
            queries_out.append({
                "library": lib["name"], "query": q["query"], "category": q["category"],
                "relevant": q["relevant_files"],
                "rank": next(rank_iter) if relevant[q_i] else None,
                "top3": [{"file": lib["paths"][a].name, "distractor": bool(lib["is_distractor"][a]),
                          "score": round(float(scores[q_i, a]), 4)} for a in top],
            })

    names = list(per_library)
    macro = {m: float(np.mean([per_library[n][m] for n in names])) for m in METRIC_COLS + ["distractor_top1"]}
    aucs = [per_library[n]["no_match_auc"] for n in names if "no_match_auc" in per_library[n]]
    return {
        "method": name,
        "route": retriever.route,
        "params_m": retriever.params_m,
        "macro": macro,
        "no_match_auc": float(np.mean(aucs)) if aucs else None,
        "ci95_R@3": bootstrap_ci(np.array(all_ranks)),
        "per_library": per_library,
        "index_ms_per_image": round(1000 * index_s / n_images, 1),
        "query_ms": round(1000 * query_s / n_queries, 1),
        "queries": queries_out,
        "captions": getattr(retriever, "captions", None) or None,
    }


# ─── Reporting ─────────────────────────────────────────────────────────────────

def _pct(x) -> str:
    return "—" if x is None else f"{100 * x:.1f}"


def summary_markdown(results: list[dict], baseline: dict, stats: dict, config: dict) -> str:
    ok = sorted((r for r in results if "error" not in r), key=lambda r: -r["macro"]["R@3"])
    libs = list(stats)
    lines = [
        "# E3 — Scene → creator asset retrieval",
        "",
        f"Run: {config['timestamp']} · device: {config['device']}",
        "",
        "## Dataset",
        "",
        "| Library | Creator photos | Distractors | Scenes with a match | Scenes with no match | Categories |",
        "|---|---|---|---|---|---|",
    ]
    for name, s in stats.items():
        lines.append(f"| {name} | {s['creator_photos']} | {s['distractors']} | {s['scenes_with_match']} | "
                     f"{s['scenes_no_match']} | {s['categories']} |")

    lines += [
        "",
        "## Overall (%)",
        "",
        "R@k / MRR over scenes that have a fitting photo. *Distractor top-1*: how often a non-creator "
        "photo won (lower is better). *No-match AUC*: how well the best score separates "
        "'a photo fits' from 'nothing fits' (100 = perfect, 50 = coin flip). Ranked by R@3.",
        "",
        "| Method | Route | Params (M) | R@1 | R@3 | R@5 | MRR | R@3 95% CI | Distractor top-1 | No-match AUC | ms/image | ms/query |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
        f"| *random* | — | — | {_pct(baseline['R@1'])} | {_pct(baseline['R@3'])} | {_pct(baseline['R@5'])} | "
        f"{_pct(baseline['MRR'])} | — | — | 50.0 | — | — |",
    ]
    for r in ok:
        m, ci = r["macro"], r["ci95_R@3"]
        lines.append(f"| {r['method']} | {r['route']} | {r['params_m'] or '—'} | {_pct(m['R@1'])} | "
                     f"{_pct(m['R@3'])} | {_pct(m['R@5'])} | {_pct(m['MRR'])} | {_pct(ci[0])}–{_pct(ci[1])} | "
                     f"{_pct(m['distractor_top1'])} | {_pct(r['no_match_auc'])} | {r['index_ms_per_image']} | "
                     f"{r['query_ms']} |")

    lines += ["", "## Fallback threshold (best similarity score below this → use stock / generation)", "",
              "Chosen on the same scenes it is scored on, so treat it as a starting value.", "",
              "| Method | Library | Threshold | Matching scenes kept | No-match scenes sent to fallback |",
              "|---|---|---|---|---|"]
    for r in ok:
        for lib, res in r["per_library"].items():
            t = res.get("threshold")
            if t:
                lines.append(f"| {r['method']} | {lib} | {t['threshold']:.3f} | {_pct(t['matches_kept'])} | "
                             f"{_pct(t['no_match_rejected'])} |")

    categories = sorted({c for r in ok for lib in r["per_library"].values() for c in lib["category_R@3"]})
    if categories:
        lines += ["", "## R@3 per scene category (%)", "",
                  "| Method | " + " | ".join(categories) + " |", "|---|" + "---|" * len(categories)]
        for r in ok:
            cats: dict[str, list[float]] = {}
            for lib in r["per_library"].values():
                for c, v in lib["category_R@3"].items():
                    cats.setdefault(c, []).append(v)
            lines.append(f"| {r['method']} | " + " | ".join(
                _pct(float(np.mean(cats[c]))) if c in cats else "—" for c in categories) + " |")

    if len(libs) > 1:
        lines += ["", "## R@3 per library (%)", "", "| Method | " + " | ".join(libs) + " |",
                  "|---|" + "---|" * len(libs)]
        for r in ok:
            lines.append(f"| {r['method']} | " + " | ".join(_pct(r["per_library"][n]["R@3"]) for n in libs) + " |")

    failed = [r for r in results if "error" in r]
    if failed:
        lines += ["", "## Methods that failed to run", ""] + [f"- {r['method']}: {r['error']}" for r in failed]
    return "\n".join(lines) + "\n"


def print_table(results: list[dict], baseline: dict) -> None:
    print("\n" + "=" * 86)
    print(f"  {'method':<22}{'R@1':>7}{'R@3':>7}{'R@5':>7}{'MRR':>7}{'distr.':>8}{'noMatchAUC':>12}{'ms/q':>8}")
    print("  " + "-" * 84)
    print(f"  {'random':<22}" + "".join(f"{_pct(baseline[m]):>7}" for m in METRIC_COLS))
    for r in sorted(results, key=lambda r: -r["macro"]["R@3"] if "error" not in r else 1):
        if "error" in r:
            print(f"  {r['method']:<22}  FAILED: {r['error'][:56]}")
            continue
        print(f"  {r['method']:<22}" + "".join(f"{_pct(r['macro'][m]):>7}" for m in METRIC_COLS)
              + f"{_pct(r['macro']['distractor_top1']):>8}{_pct(r['no_match_auc']):>12}{r['query_ms']:>8}")
    print("=" * 86)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--methods", nargs="*", help="methods to run (default: all)")
    parser.add_argument("--quick", action="store_true", help=f"only {', '.join(QUICK_METHODS)}")
    parser.add_argument("--libraries", nargs="*", help="library folder names in data/ (default: all)")
    parser.add_argument("--tag", default="", help="suffix for output files")
    args = parser.parse_args()

    if not DATA_DIR.exists():
        raise SystemExit(f"No data folder at {DATA_DIR} — see README.md")
    lib_dirs = sorted(d for d in DATA_DIR.iterdir() if (d / "queries.csv").exists())
    if args.libraries:
        lib_dirs = [d for d in lib_dirs if d.name in args.libraries]
    if not lib_dirs:
        raise SystemExit(f"No library folders with queries.csv in {DATA_DIR}")

    libraries = [load_library(d) for d in lib_dirs]
    stats = {lib["name"]: library_stats(lib) for lib in libraries}
    for name, s in stats.items():
        print(f"[E3] {name}: {s['creator_photos']} creator photos + {s['distractors']} distractors, "
              f"{s['scenes_with_match']} scenes with a match, {s['scenes_no_match']} without")
        if s["scenes_no_match"] == 0:
            print(f"[E3] WARNING {name}: no 'no match' scenes — the fallback threshold cannot be measured")

    per_lib_baselines = [random_baseline(len(lib["images"]), lib["relevant"]) for lib in libraries]
    baseline = {m: float(np.mean([b[m] for b in per_lib_baselines])) for m in METRIC_COLS}

    import torch
    methods = args.methods or (QUICK_METHODS if args.quick else DEFAULT_METHODS)
    config = {"timestamp": datetime.now().isoformat(timespec="seconds"),
              "device": "cuda" if torch.cuda.is_available() else "cpu",
              "python": platform.python_version(), "methods": methods}

    results = []
    for name in methods:
        print(f"[E3] {name} ...", flush=True)
        try:
            results.append(evaluate_method(name, libraries))
        except Exception as exc:   # e.g. model download failed — keep the other methods
            print(f"[E3] {name} FAILED: {exc}")
            results.append({"method": name, "error": f"{type(exc).__name__}: {exc}"})

    print_table(results, baseline)

    RESULTS_DIR.mkdir(exist_ok=True)
    suffix = f"_{args.tag}" if args.tag else ""
    json_path = RESULTS_DIR / f"e3_results{suffix}.json"
    md_path = RESULTS_DIR / f"e3_summary{suffix}.md"
    json_path.write_text(json.dumps({"config": config, "dataset": stats, "random_baseline": baseline,
                                     "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(summary_markdown(results, baseline, stats, config), encoding="utf-8")
    print(f"[E3] Saved {json_path.relative_to(HERE)} and {md_path.relative_to(HERE)}")


if __name__ == "__main__":
    main()
