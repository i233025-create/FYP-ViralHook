"""
make_topic_sheet.py — Labelling sheet for topic queries (E1 v2)
================================================================
In the real pipeline the retriever is queried with a TOPIC from the Research
Agent, not with an Instagram caption. Captions are often empty or teasers
("Who knew this?"), so E1 v2 adds hand-written topic queries.

This writes data/<creator>/topics.csv with one row per transcribed reel:

  file, transcript_preview, topic   <- the labeller fills in `topic`

Run after prepare_data.py. Open the CSV in Excel (it is UTF-8 with BOM so
Urdu shows correctly), fill the `topic` column, save as CSV. Re-running keeps
topics already written and only adds new reels.

Labelling rules (put these in front of whoever labels):
  1. Watch the reel (file name = ig_<code>.mp4, or instagram.com/reel/<code>/)
     or read the preview, then write what the reel is ABOUT, in your own words,
     the way you would pitch it as a content idea: 5-15 words.
       good: "Trying the famous kulfi in Sahiwal with a friend"
       good: "Why Pakistanis keep getting visa rejections"
       bad:  "Kharcha hogaya ustaad"      (teaser, says nothing)
  2. Do NOT look at the Instagram caption, and do not copy sentences from the
     transcript. Names of places / dishes / products are fine if they are the
     topic of the reel.
  3. English or Roman Urdu, whatever is natural. Leave `topic` empty for a reel
     with no real topic (pure music, meme with no speech) — it then stays in
     the library as a distractor but is not used as a query.

Usage:
  python make_topic_sheet.py --creators "Rabika Tahir v2" "Hamza Bhatti v2" "Tech Wisdom v2"
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from prepare_data import DATA_DIR, TRANSCRIPTS_FILE, read_captions
from run_e1 import MIN_TRANSCRIPT_WORDS, TOPICS_FILE, read_topics
from text_clean import word_count

PREVIEW_CHARS = 300


def build_rows(creator_dir: Path, transcripts_name: str = TRANSCRIPTS_FILE) -> list[dict]:
    """One row per reel that will be in the library; existing topics are kept."""
    path = creator_dir / transcripts_name
    if not path.exists():
        raise SystemExit(f"{path} not found — run prepare_data.py first")
    transcripts = json.loads(path.read_text(encoding="utf-8"))
    existing = read_topics(creator_dir)

    rows = []
    for row in read_captions(creator_dir):
        text = (transcripts.get(row["file"]) or {}).get("text", "")
        if word_count(text) < MIN_TRANSCRIPT_WORDS:
            continue  # not in the library, no point labelling it
        preview = text[:PREVIEW_CHARS] + ("..." if len(text) > PREVIEW_CHARS else "")
        rows.append({"file": row["file"], "transcript_preview": preview, "topic": existing.get(row["file"], "")})
    return rows


def write_sheet(creator_dir: Path, rows: list[dict]) -> Path:
    out = creator_dir / TOPICS_FILE
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["file", "transcript_preview", "topic"])
        writer.writeheader()
        writer.writerows(rows)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--creators", nargs="+", required=True, help="creator folder names under data/")
    parser.add_argument("--transcripts", default=TRANSCRIPTS_FILE, help="transcripts file in each creator folder")
    args = parser.parse_args()

    for name in args.creators:
        creator_dir = DATA_DIR / name
        rows = build_rows(creator_dir, args.transcripts)
        out = write_sheet(creator_dir, rows)
        done = sum(1 for r in rows if r["topic"])
        print(f"[topics] {name}: {len(rows)} reels, {done} already labelled -> {out}")


if __name__ == "__main__":
    main()
