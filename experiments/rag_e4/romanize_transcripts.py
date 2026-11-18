"""
romanize_transcripts.py — Urdu-script transcripts → Roman Urdu (E4 step 2)
===========================================================================
Reads, per creator folder in experiments/rag_e1/data/:
  <urdu file>      Whisper language="ur" transcripts (prepare_data.py --language ur)
  <english file>   Whisper language="en" transcripts of the same reels (hint)
Writes <out file>:
  {"ig_x.mp4": {"text": <Roman Urdu>, "source": <urdu file>, "llm": <model>,
                "arabic_share_in": 0.97, "arabic_share_out": 0.0, "error": null}}

Uses pipeline.urdu_style.romanize (local Ollama). Already-converted reels are
skipped unless --force or a different --llm; progress is saved after every reel.

Usage (from experiments/rag_e4/):
  python romanize_transcripts.py --creators "Hamza Bhatti" --urdu transcripts_small_ur.json --limit 3
  python romanize_transcripts.py --urdu transcripts_turbo_ur.json --llm qwen2.5:14b \
      --out transcripts_turbo_roman.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.urdu_style import RomanizeError, arabic_script_share, romanize  # noqa: E402

DATA_DIR = HERE.parent / "rag_e1" / "data"
ENGLISH_FILE = "transcripts_small_en.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def romanize_creator(creator_dir: Path, urdu_name: str, english_name: str, out_name: str,
                     llm: str | None, limit: int | None, force: bool, convert=romanize) -> dict:
    urdu = _load(creator_dir / urdu_name)
    if not urdu:
        print(f"[romanize] {creator_dir.name}: no {urdu_name} — skipped")
        return {}
    english = _load(creator_dir / english_name)
    out_path = creator_dir / out_name
    done = _load(out_path)

    files = list(urdu)[:limit] if limit else list(urdu)
    todo = [f for f in files if force or f not in done or done[f].get("llm") != llm or done[f].get("error")]
    print(f"\n[romanize] {creator_dir.name}: {len(files)} reels, {len(todo)} to convert")
    for i, name in enumerate(todo, start=1):
        text = (urdu[name] or {}).get("text", "")
        hint = (english.get(name) or {}).get("text", "")
        started = time.time()
        record = {"source": urdu_name, "llm": llm, "arabic_share_in": round(arabic_script_share(text), 3)}
        try:
            roman = convert(text, hint, model=llm)
            record.update({"text": roman, "error": None})
        except RomanizeError as e:
            record.update({"text": "", "error": str(e)})
        record["arabic_share_out"] = round(arabic_script_share(record["text"]), 3)
        done[name] = record
        out_path.write_text(json.dumps(done, ensure_ascii=False, indent=2), encoding="utf-8")
        status = record["error"] or record["text"][:140]
        print(f"  [{i}/{len(todo)}] {name}: {time.time() - started:.0f}s  {status}")
    return done


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--creators", nargs="*", help="creator folder names (default: all with the Urdu file)")
    parser.add_argument("--urdu", default="transcripts_turbo_ur.json", help="Urdu-script transcripts file")
    parser.add_argument("--english", default=ENGLISH_FILE, help="English transcripts file (hint)")
    parser.add_argument("--out", default=None, help="output file (default: <urdu file> with _ur → _roman)")
    parser.add_argument("--llm", default=None, help="Ollama model (default: OLLAMA_MODEL from .env)")
    parser.add_argument("--limit", type=int, default=None, help="only the first N reels per creator")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    out_name = args.out or args.urdu.replace("_ur.json", "_roman.json")
    if out_name == args.urdu:
        raise SystemExit("--out must differ from --urdu")
    dirs = sorted(d for d in DATA_DIR.iterdir() if (d / args.urdu).exists())
    if args.creators:
        dirs = [d for d in dirs if d.name in args.creators]
    if not dirs:
        raise SystemExit(f"No creator folder in {DATA_DIR} has {args.urdu} — run prepare_data.py --language ur")
    for d in dirs:
        romanize_creator(d, args.urdu, args.english, out_name, args.llm, args.limit, args.force)


if __name__ == "__main__":
    main()
