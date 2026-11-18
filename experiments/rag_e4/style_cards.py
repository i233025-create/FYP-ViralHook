"""
style_cards.py — Measured style card per creator (E4 step 3)
=============================================================
For each creator folder: Roman Urdu transcripts (+ English transcripts of the
same reels, + creator-written captions) → pipeline.urdu_style.style_card().
Other creators' Roman transcripts are the background, so catchphrases are
the ones distinctive to this creator.

Writes results/e4_style_cards_<tag>.md (tables) and .json (full cards).
The .md quotes short catchphrases — check them before committing.

Usage (from experiments/rag_e4/):
  python style_cards.py --roman transcripts_turbo_roman.json --tag turbo
  python style_cards.py --roman transcripts_small_roman.json --creators "Hamza Bhatti" "Rabika Tahir" --tag small
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent))
from pipeline.urdu_style import card_prompt, style_card  # noqa: E402

DATA_DIR = HERE.parent / "rag_e1" / "data"
RESULTS_DIR = HERE / "results"
MIN_WORDS = 10      # same floor as E1 / the Scripting Agent for a usable transcript


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_creator(creator_dir: Path, roman_name: str, english_name: str) -> dict:
    roman = _load(creator_dir / roman_name)
    english = _load(creator_dir / english_name)
    captions = {}
    path = creator_dir / "captions.csv"
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as f:
            captions = {r["file"].strip(): r.get("caption") or "" for r in csv.DictReader(f)}
    files = [f for f, r in roman.items() if len((r or {}).get("text", "").split()) >= MIN_WORDS]
    return {
        "files": files,
        "roman": [roman[f]["text"] for f in files],
        "english": [(english.get(f) or {}).get("text", "") for f in files],
        "captions": [captions[f] for f in captions if captions[f].strip()],
    }


def build_cards(creators: dict[str, dict]) -> dict[str, dict]:
    cards = {}
    for name, data in creators.items():
        background = [t for other, d in creators.items() if other != name for t in d["roman"]]
        cards[name] = style_card(data["roman"], data["english"], data["captions"], background)
    return cards


def to_markdown(cards: dict[str, dict], roman_name: str) -> str:
    lines = [f"# E4 — Creator style cards ({roman_name})", "",
             f"Run: {time.strftime('%Y-%m-%dT%H:%M:%S')} · background for catchphrases: the other creators", "",
             "| Creator | Reels | Words | English % | Hook / body / end English % | Avg sentence words "
             "| Address (per 100 words) | Caption English % |",
             "|---|---|---|---|---|---|---|---|"]
    for name, c in cards.items():
        if not c.get("reels"):
            lines.append(f"| {name} | 0 | — | — | — | — | — | — |")
            continue
        p = c["english_ratio_by_part"]
        address = ", ".join(f"{k} {v}" for k, v in list(c["address"].items())[:4]) or "—"
        written = c.get("written", {}).get("english_ratio")
        lines.append(f"| {name} | {c['reels']} | {c['words']} | {100 * c['english_ratio']:.1f} | "
                     f"{100 * p['hook']:.0f} / {100 * p['body']:.0f} / {100 * p['end']:.0f} | "
                     f"{c['avg_sentence_words']} | {address} | "
                     f"{'—' if written is None else f'{100 * written:.1f}'} |")
    for name, c in cards.items():
        if not c.get("reels"):
            continue
        lines += ["", f"## {name}", ""]
        if c["catchphrases"]:
            lines += ["| Catchphrase | Reels | Share | Other creators |", "|---|---|---|---|"]
            lines += [f"| {x['phrase']} | {x['reels']} | {100 * x['share']:.0f}% | "
                      f"{100 * x['background_share']:.0f}% |" for x in c["catchphrases"]]
        else:
            lines.append("No catchphrase repeated in 2+ reels.")
        for key in ("openers", "closers"):
            if c[key]:
                lines.append(f"\n{key.title()}: " + ", ".join(f"\"{o['phrase']}\" ({o['reels']})" for o in c[key]))
        lines += ["", "Prompt text:", "", "> " + card_prompt(c)]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--roman", default="transcripts_turbo_roman.json")
    parser.add_argument("--english", default="transcripts_small_en.json")
    parser.add_argument("--creators", nargs="*")
    parser.add_argument("--tag", default="v1")
    args = parser.parse_args()

    dirs = sorted(d for d in DATA_DIR.iterdir() if (d / args.roman).exists())
    if args.creators:
        dirs = [d for d in dirs if d.name in args.creators]
    if not dirs:
        raise SystemExit(f"No creator folder has {args.roman} — run romanize_transcripts.py first")
    creators = {d.name: load_creator(d, args.roman, args.english) for d in dirs}
    cards = build_cards(creators)

    RESULTS_DIR.mkdir(exist_ok=True)
    md = RESULTS_DIR / f"e4_style_cards_{args.tag}.md"
    md.write_text(to_markdown(cards, args.roman), encoding="utf-8")
    (RESULTS_DIR / f"e4_style_cards_{args.tag}.json").write_text(
        json.dumps(cards, ensure_ascii=False, indent=2), encoding="utf-8")
    print(md.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
