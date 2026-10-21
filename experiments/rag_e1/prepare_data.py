"""
prepare_data.py — Transcribe each creator's downloaded reels (E1 step 1)
=========================================================================
Expected layout (one folder per creator):

  experiments/rag_e1/data/
    hashaam/
      captions.csv        columns: file,caption
      reel_01.mp4
      reel_02.mp4
    tech_creator/
      ...

Writes data/<creator>/transcripts.json:
  {"reel_01.mp4": {"text": ..., "language": "en", "language_prob": 0.97,
                   "script": {"latin": 0.9, "arabic": 0.1, ...},
                   "whisper_model": "small", "forced_language": null}}

Already-transcribed files are skipped unless --force, or unless they were
made with a different --model / --language (so switching settings re-runs).

Usage:
  python prepare_data.py                                  # all creators, Whisper small
  python prepare_data.py --creators hashaam --limit 3     # check Whisper output on 3 reels first
  python prepare_data.py --creators hashaam --model medium --language ur
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

from text_clean import detect_script, dominant_script, word_count

HERE = Path(__file__).parent
DATA_DIR = HERE / "data"
CAPTIONS_FILE = "captions.csv"
TRANSCRIPTS_FILE = "transcripts.json"


def read_captions(creator_dir: Path) -> list[dict]:
    """captions.csv → [{"file": ..., "caption": ...}] (utf-8, BOM tolerated)."""
    path = creator_dir / CAPTIONS_FILE
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    missing = {"file", "caption"} - set(rows[0].keys() if rows else [])
    if missing:
        raise SystemExit(f"{path}: missing column(s) {sorted(missing)} — expected header 'file,caption'")
    return [{"file": r["file"].strip(), "caption": r["caption"] or ""} for r in rows if r["file"].strip()]


def load_whisper(model_size: str):
    from faster_whisper import WhisperModel
    try:
        import ctranslate2
        on_gpu = ctranslate2.get_cuda_device_count() > 0
    except Exception:
        on_gpu = False
    device, compute = ("cuda", "float16") if on_gpu else ("cpu", "int8")
    print(f"[prepare] Loading Whisper '{model_size}' on {device} ({compute})...")
    return WhisperModel(model_size, device=device, compute_type=compute)


def transcribe(model, video: Path, language: str | None) -> dict:
    segments, info = model.transcribe(str(video), language=language, vad_filter=True, beam_size=5)
    text = " ".join(s.text.strip() for s in segments).strip()
    return {
        "text": text,
        "language": info.language,
        "language_prob": round(info.language_probability, 3),
        "script": detect_script(text),
    }


def prepare_creator(creator_dir: Path, model_size: str, language: str | None,
                    limit: int | None, force: bool, get_model, out_name: str = TRANSCRIPTS_FILE) -> None:
    rows = read_captions(creator_dir)
    out_path = creator_dir / out_name
    done = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}

    todo = []
    for row in rows[:limit] if limit else rows:
        prev = done.get(row["file"])
        stale = prev is None or prev.get("whisper_model") != model_size or prev.get("forced_language") != language
        if force or stale:
            todo.append(row)
    print(f"\n[prepare] {creator_dir.name}: {len(rows)} reels in captions.csv, {len(todo)} to transcribe")

    for i, row in enumerate(todo, start=1):
        video = creator_dir / row["file"]
        if not video.exists():
            print(f"  [{i}/{len(todo)}] {row['file']}: FILE NOT FOUND — skipped")
            continue
        started = time.time()
        result = transcribe(get_model(), video, language)
        result.update({"whisper_model": model_size, "forced_language": language})
        done[row["file"]] = result
        # Save after every file so an interrupted run keeps its progress.
        out_path.write_text(json.dumps(done, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [{i}/{len(todo)}] {row['file']}: {word_count(result['text'])} words, "
              f"lang={result['language']} ({result['language_prob']}), "
              f"script={dominant_script(result['text'])} {result['script']}, {time.time() - started:.0f}s")
        print(f"      {result['text'][:160]}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--creators", nargs="*", help="creator folder names (default: all in data/)")
    parser.add_argument("--model", default="small", help="Whisper size: tiny/base/small/medium/large-v3")
    parser.add_argument("--language", default=None, help="force a language code (e.g. en, ur); default auto-detect")
    parser.add_argument("--limit", type=int, default=None, help="only the first N reels per creator")
    parser.add_argument("--force", action="store_true", help="re-transcribe even if cached")
    parser.add_argument("--out", default=TRANSCRIPTS_FILE,
                        help="transcripts file name, to keep several Whisper settings side by side "
                             "(e.g. transcripts_medium_en.json); run_e1.py --transcripts reads it")
    args = parser.parse_args()

    if not DATA_DIR.exists():
        raise SystemExit(f"No data folder at {DATA_DIR} — see README.md for the layout")
    creator_dirs = sorted(d for d in DATA_DIR.iterdir() if (d / CAPTIONS_FILE).exists())
    if args.creators:
        creator_dirs = [d for d in creator_dirs if d.name in args.creators]
    if not creator_dirs:
        raise SystemExit(f"No creator folders with {CAPTIONS_FILE} found in {DATA_DIR}")

    model = None

    def get_model():
        nonlocal model
        if model is None:
            model = load_whisper(args.model)
        return model

    for creator_dir in creator_dirs:
        prepare_creator(creator_dir, args.model, args.language, args.limit, args.force, get_model, args.out)


if __name__ == "__main__":
    main()
