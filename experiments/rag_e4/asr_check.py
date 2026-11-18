"""
asr_check.py — How close is each Roman Urdu transcript to what was said? (E4 step 4)
=====================================================================================
Two steps:

  sheet   pick N reels per creator that every variant transcribed and write
          data/e4_reference_sheet.csv (git-ignored: it holds transcripts):
            creator, file, reel_url, <one column per variant>, draft_from, reference
          `reference` is pre-filled with ONE variant chosen at random per row
          (named in draft_from), so no variant is favoured by being the draft.

  score   after a human has corrected `reference` while listening to the reel,
          compare every variant against it:
            WER           word error rate after Roman Urdu spelling
                          normalisation (hai/hay/he → hai, nahin/nai → nahi, ...)
            English % err |English share(variant) − English share(reference)|
                          — the code-switch number the style card uses
          → results/e4_asr_<tag>.md (only numbers, safe to commit).

Labelling rules for `reference`:
  1. Listen to the whole reel (instagram.com/reel/<code>/ or the .mp4).
  2. Write what was said in Roman Urdu; English words in normal English spelling.
     Do not translate, do not fix the speaker's grammar.
  3. Spelling does not need to be perfect (it is normalised), but every word
     must be there, in order.
  4. Leave `reference` empty to skip a reel (music only, unclear audio).

Usage (from experiments/rag_e4/):
  python asr_check.py sheet --variants small=transcripts_small_roman.json \
      turbo=transcripts_turbo_roman.json prompt=transcripts_turbo_prompt.json --per-creator 4
  python asr_check.py score --tag v1
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent))
from pipeline.urdu_style import english_ratio, tokens  # noqa: E402

DATA_DIR = HERE.parent / "rag_e1" / "data"
SHEET = DATA_DIR / "e4_reference_sheet.csv"
RESULTS_DIR = HERE / "results"
MIN_WORDS = 10
BOOTSTRAP = 2000

# Roman Urdu has no standard spelling; map common variants to one form.
SPELLING = {
    "hay": "hai", "he": "hai", "hy": "hai", "hain": "hain", "hen": "hain", "hein": "hain",
    "nahin": "nahi", "nai": "nahi", "nhi": "nahi", "nahee": "nahi",
    "mein": "main", "me": "main", "mai": "main", "mien": "main",
    "kia": "kya", "kiya": "kya", "kyu": "kyun", "kyon": "kyun",
    "tou": "to", "toh": "to", "bhi": "bhi", "bi": "bhi",
    "yeh": "ye", "yah": "ye", "woh": "wo", "vo": "wo", "voh": "wo",
    "ap": "aap", "apka": "aapka", "apki": "aapki", "apke": "aapke", "apko": "aapko",
    "bohat": "bahut", "boht": "bahut", "bht": "bahut", "bohot": "bahut",
    "acha": "accha", "achha": "accha", "kay": "ke", "say": "se",
    "aik": "ek", "zyada": "ziada", "zada": "ziada", "phir": "phir", "fir": "phir",
}


def normalise(text: str) -> list[str]:
    words = []
    for w in tokens(text):
        w = re.sub(r"(.)\1{2,}", r"\1\1", w)          # "bahuuut" → "bahuut"
        w = re.sub(r"([aeiou])\1", r"\1", w) if w not in SPELLING else w   # aa/ee/oo → a/e/o
        words.append(SPELLING.get(w, w))
    return words


def wer(hypothesis: str, reference: str) -> float:
    """Word error rate (Levenshtein over normalised words) / reference length."""
    h, r = normalise(hypothesis), normalise(reference)
    if not r:
        return 0.0 if not h else 1.0
    prev = list(range(len(h) + 1))
    for i, rw in enumerate(r, 1):
        cur = [i] + [0] * len(h)
        for j, hw in enumerate(h, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (rw != hw))
        prev = cur
    return prev[-1] / len(r)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def make_sheet(variants: dict[str, str], per_creator: int, seed: int, creators: list[str] | None) -> int:
    rng = random.Random(seed)
    rows = []
    for d in sorted(p for p in DATA_DIR.iterdir() if p.is_dir()):
        if creators and d.name not in creators:
            continue
        loaded = {name: _load(d / f) for name, f in variants.items()}
        if not all(loaded.values()):
            continue
        common = [f for f in loaded[next(iter(variants))]
                  if all(len((v.get(f) or {}).get("text", "").split()) >= MIN_WORDS for v in loaded.values())]
        for f in rng.sample(sorted(common), min(per_creator, len(common))):
            draft = rng.choice(list(variants))
            code = re.sub(r"^ig_|\.mp4$", "", f)
            row = {"creator": d.name, "file": f,
                   "reel_url": f"https://www.instagram.com/reel/{code}/" if f.startswith("ig_") else ""}
            row.update({name: loaded[name][f]["text"] for name in variants})
            row.update({"draft_from": draft, "reference": loaded[draft][f]["text"]})
            rows.append(row)
    if not rows:
        raise SystemExit("No reel has all variants — check the --variants files exist per creator")
    if SHEET.exists():
        raise SystemExit(f"{SHEET} exists — move it away first (it may hold your corrections)")
    with SHEET.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} reels to {SHEET}. Correct the `reference` column while listening.")
    return len(rows)


def _ci(values: list[float], rng: random.Random) -> tuple[float, float]:
    means = sorted(sum(rng.choice(values) for _ in values) / len(values) for _ in range(BOOTSTRAP))
    return means[int(0.025 * BOOTSTRAP)], means[int(0.975 * BOOTSTRAP) - 1]


def score(tag: str) -> str:
    with SHEET.open(encoding="utf-8-sig", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if (r.get("reference") or "").strip()]
    if not rows:
        raise SystemExit("No row has a reference yet")
    fixed = {"creator", "file", "reel_url", "draft_from", "reference"}
    variants = [c for c in rows[0] if c not in fixed]
    rng = random.Random(0)
    lines = [f"# E4 — Roman Urdu transcript accuracy ({tag})", "",
             f"Run: {time.strftime('%Y-%m-%dT%H:%M:%S')} · {len(rows)} reels with a human reference · "
             f"creators: {', '.join(sorted({r['creator'] for r in rows}))}", "",
             "WER after spelling normalisation (lower is better), 95% bootstrap CI. "
             "*Draft rows*: reels whose reference was pre-filled from this variant "
             "(the labeller corrected it, so it may be slightly favoured there).", "",
             "| Variant | WER % | WER 95% CI | English-share error (pts) | Draft rows | Best on reels |",
             "|---|---|---|---|---|---|"]
    per_row = {v: [wer(r[v], r["reference"]) for r in rows] for v in variants}
    best = [min(variants, key=lambda v: per_row[v][i]) for i in range(len(rows))]
    for v in sorted(variants, key=lambda v: sum(per_row[v])):
        values = per_row[v]
        low, high = _ci(values, rng)
        en_err = [abs(english_ratio(r[v]) - english_ratio(r["reference"])) for r in rows]
        lines.append(f"| {v} | {100 * sum(values) / len(values):.1f} | {100 * low:.1f}–{100 * high:.1f} | "
                     f"{100 * sum(en_err) / len(en_err):.1f} | {sum(r['draft_from'] == v for r in rows)} | "
                     f"{best.count(v)} |")
    RESULTS_DIR.mkdir(exist_ok=True)
    text = "\n".join(lines) + "\n"
    (RESULTS_DIR / f"e4_asr_{tag}.md").write_text(text, encoding="utf-8")
    print(text)
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sheet")
    s.add_argument("--variants", nargs="+", required=True, help="name=transcripts file (Roman Urdu)")
    s.add_argument("--per-creator", type=int, default=4)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--creators", nargs="*")
    c = sub.add_parser("score")
    c.add_argument("--tag", default="v1")
    args = parser.parse_args()
    if args.cmd == "sheet":
        variants = dict(v.split("=", 1) for v in args.variants)
        make_sheet(variants, args.per_creator, args.seed, args.creators)
    else:
        score(args.tag)


if __name__ == "__main__":
    main()
