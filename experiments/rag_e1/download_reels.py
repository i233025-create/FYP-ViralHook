"""
download_reels.py — Step 2: download reels listed by collect_reels.js
=====================================================================
Replaces the manual savefrom.net step.

  Step 1 (browser): paste collect_reels.js into the DevTools Console on
          instagram.com → Downloads/<username>_reels.json (captions + video links)
  Step 2 (this):    download every video into the layout prepare_data.py expects

  data/<creator>/
    captions.csv          file,caption   (full caption, not cut at ~100 chars)
    ig_<shortcode>.mp4

Listing happens inside the real browser session, so Instagram sees normal use;
this script only fetches the video files from Instagram's CDN and needs no
login or cookies. CDN links expire after a few hours: run this soon after step 1
(if downloads fail with 403, just run step 1 again).

Re-running is safe: reels already listed in captions.csv and present on disk
are skipped.

Usage:
  python download_reels.py --json "%USERPROFILE%\\Downloads\\rabikaatahir_reels.json" --creator "Rabika Tahir v2"

Then:  python prepare_data.py --creators "Rabika Tahir v2" --language en
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
DATA_DIR = HERE / "data"
CAPTIONS_FILE = "captions.csv"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")


# ─── captions.csv helpers ──────────────────────────────────────────────────────

def read_captions(path: Path) -> dict[str, str]:
    """Existing captions.csv → {file: caption}; empty if the file is missing."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {r["file"].strip(): r["caption"] or "" for r in csv.DictReader(f) if r.get("file", "").strip()}


def write_captions(path: Path, captions: dict[str, str]) -> None:
    """Write {file: caption} as captions.csv. utf-8-sig so Excel shows Urdu correctly."""
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["file", "caption"])
        writer.writerows(captions.items())
    tmp.replace(path)


def reel_filename(shortcode: str) -> str:
    return f"ig_{shortcode}.mp4"


def already_have(creator_dir: Path, captions: dict[str, str], shortcode: str) -> bool:
    """True if this reel is both listed in captions.csv and on disk."""
    name = reel_filename(shortcode)
    return name in captions and (creator_dir / name).exists()


def load_reels(path: Path) -> list[dict]:
    """collect_reels.js output → [{shortcode, caption, video_url}], duplicates dropped."""
    data = json.loads(path.read_text(encoding="utf-8"))
    seen, reels = set(), []
    for r in data.get("reels", []):
        code, url = r.get("shortcode"), r.get("video_url")
        if code and url and code not in seen:
            seen.add(code)
            reels.append({"shortcode": code, "caption": r.get("caption") or "", "video_url": url})
    return reels


# ─── Download ─────────────────────────────────────────────────────────────────

def download_file(session, url: str, dest: Path) -> None:
    tmp = dest.with_suffix(".part")
    with session.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with tmp.open("wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
    tmp.replace(dest)


def download_all(reels: list[dict], creator_dir: Path, sleep: float) -> None:
    import requests

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Referer": "https://www.instagram.com/"})
    csv_path = creator_dir / CAPTIONS_FILE
    captions = read_captions(csv_path)
    failed = 0

    for i, reel in enumerate(reels, start=1):
        code, name = reel["shortcode"], reel_filename(reel["shortcode"])
        if already_have(creator_dir, captions, code):
            print(f"  [{i}/{len(reels)}] {code}: already downloaded")
            continue
        try:
            download_file(session, reel["video_url"], creator_dir / name)
        except Exception as exc:  # one broken reel should not stop the run
            failed += 1
            print(f"  [{i}/{len(reels)}] {code}: FAILED — {exc}")
            continue
        captions[name] = reel["caption"]
        write_captions(csv_path, captions)
        print(f"  [{i}/{len(reels)}] {name}: {reel['caption'][:70]!r}")
        if sleep > 0:
            time.sleep(random.uniform(sleep, sleep * 2))

    if failed:
        print(f"\n[download] {failed} failed. If they are 403 errors the links expired: "
              "run collect_reels.js again and re-run this (finished reels are skipped).")


def main():
    # Windows consoles default to cp1252 and crash on emoji in captions.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", required=True, type=Path, help="<username>_reels.json from collect_reels.js")
    parser.add_argument("--creator", required=True, help="folder name under data/ (e.g. 'Rabika Tahir v2')")
    parser.add_argument("--sleep", type=float, default=0.5, help="min seconds between downloads (default 0.5)")
    args = parser.parse_args()

    reels = load_reels(args.json)
    creator_dir = DATA_DIR / args.creator
    creator_dir.mkdir(parents=True, exist_ok=True)
    print(f"[download] {len(reels)} reels in {args.json.name} → {creator_dir}")
    download_all(reels, creator_dir, args.sleep)

    total = len(read_captions(creator_dir / CAPTIONS_FILE))
    print(f"\n[download] {creator_dir.name}: {total} reels in captions.csv")
    print(f"Next: python prepare_data.py --creators \"{args.creator}\" --language en")


if __name__ == "__main__":
    main()
