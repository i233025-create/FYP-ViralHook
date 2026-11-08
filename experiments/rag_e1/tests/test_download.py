"""Unit tests for download_reels.py helpers — no network. Run: python -m pytest tests"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from download_reels import already_have, load_reels, read_captions, reel_filename, write_captions


def test_captions_roundtrip_keeps_urdu_commas_and_newlines(tmp_path):
    path = tmp_path / "captions.csv"
    data = {"ig_a.mp4": "Chapli Kabab, Peshawar\nbest in town", "ig_b.mp4": "روزہ لگ رہا ہے"}
    write_captions(path, data)
    assert read_captions(path) == data


def test_read_captions_missing_file_is_empty(tmp_path):
    assert read_captions(tmp_path / "nope.csv") == {}


def test_already_have_needs_csv_entry_and_file(tmp_path):
    captions = {reel_filename("abc"): "x"}
    assert not already_have(tmp_path, captions, "abc")      # listed, not on disk
    (tmp_path / reel_filename("abc")).write_bytes(b"")
    assert already_have(tmp_path, captions, "abc")
    assert not already_have(tmp_path, captions, "ab")       # different shortcode


def test_load_reels_drops_duplicates_and_incomplete_rows(tmp_path):
    path = tmp_path / "x_reels.json"
    path.write_text(json.dumps({"profile": "x", "reels": [
        {"shortcode": "A", "caption": "Glow serum", "video_url": "u1"},
        {"shortcode": "A", "caption": "dup", "video_url": "u1"},
        {"shortcode": "B", "caption": None, "video_url": "u2"},
        {"shortcode": "C", "caption": "no url"},
    ]}), encoding="utf-8")
    assert load_reels(path) == [
        {"shortcode": "A", "caption": "Glow serum", "video_url": "u1"},
        {"shortcode": "B", "caption": "", "video_url": "u2"},
    ]
