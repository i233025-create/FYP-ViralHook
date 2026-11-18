"""E4: Roman Urdu transcripts, style cards, ASR check — no models, no LLM."""

import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import asr_check  # noqa: E402
import romanize_transcripts as rt  # noqa: E402
import style_cards  # noqa: E402

ROMAN = ["Dosto aaj hum Pindi mein hain. Yeh shop bohat famous hai. Bas yahi tha aaj ka dosto.",
         "Dosto aaj hum Lahore mein hain. Khana bohat acha hai yaar. Bas yahi tha aaj ka dosto."]


def _write(path: Path, data: dict):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_wer_normalises_roman_spelling():
    assert asr_check.wer("yeh bohat acha hay", "ye bahut accha hai") == 0.0
    assert asr_check.wer("aaj hum shop par", "aaj hum shop par hain") == pytest.approx(1 / 5)
    assert asr_check.wer("", "") == 0.0


def test_romanize_creator_saves_and_skips_done(tmp_path):
    _write(tmp_path / "ur.json", {"a.mp4": {"text": "آج ہم"}, "b.mp4": {"text": "شوپ"}})
    _write(tmp_path / "en.json", {"a.mp4": {"text": "today we"}})
    calls = []

    def fake(text, hint, model=None):
        calls.append(hint)
        return "aaj hum"

    done = rt.romanize_creator(tmp_path, "ur.json", "en.json", "roman.json", None, None, False, fake)
    assert done["a.mp4"]["text"] == "aaj hum" and calls == ["today we", ""]
    rt.romanize_creator(tmp_path, "ur.json", "en.json", "roman.json", None, None, False, fake)
    assert len(calls) == 2                       # cached
    saved = json.loads((tmp_path / "roman.json").read_text(encoding="utf-8"))
    assert saved["b.mp4"]["arabic_share_in"] == 1.0 and saved["b.mp4"]["arabic_share_out"] == 0.0


def test_romanize_creator_records_failures(tmp_path):
    _write(tmp_path / "ur.json", {"a.mp4": {"text": "آج ہم"}})

    def broken(text, hint, model=None):
        raise rt.RomanizeError("still Urdu script")

    done = rt.romanize_creator(tmp_path, "ur.json", "en.json", "roman.json", None, None, False, broken)
    assert done["a.mp4"]["error"] == "still Urdu script" and done["a.mp4"]["text"] == ""


def test_style_cards_use_other_creators_as_background(tmp_path):
    creators = {
        "A": {"roman": ROMAN, "english": ["", ""], "captions": ["Ye hai Pindi #pindi"]},
        "B": {"roman": ["Dosto aaj hum ghar par hain bas", "Dosto aaj hum bahar hain bas"],
              "english": ["", ""], "captions": []},
    }
    cards = style_cards.build_cards(creators)
    phrases = [c["phrase"] for c in cards["A"]["catchphrases"]]
    assert cards["A"]["closers"][0]["phrase"] == "bas yahi tha aaj ka"   # sign-off, own slot
    assert not any(p.startswith("dosto aaj hum") for p in phrases)   # B says it too
    md = style_cards.to_markdown(cards, "roman.json")
    assert "| A | 2 |" in md and "Prompt text" in md


def test_load_creator_skips_short_transcripts(tmp_path):
    _write(tmp_path / "roman.json", {"a.mp4": {"text": ROMAN[0]}, "b.mp4": {"text": "bas"}})
    with (tmp_path / "captions.csv").open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows([["file", "caption"], ["a.mp4", "Pindi"], ["b.mp4", ""]])
    data = style_cards.load_creator(tmp_path, "roman.json", "en.json")
    assert data["files"] == ["a.mp4"] and data["captions"] == ["Pindi"]


def test_sheet_and_score(tmp_path, monkeypatch):
    data = tmp_path / "data"
    (data / "A").mkdir(parents=True)
    _write(data / "A" / "x.json", {"ig_1.mp4": {"text": ROMAN[0]}, "ig_2.mp4": {"text": ROMAN[1]}})
    _write(data / "A" / "y.json", {"ig_1.mp4": {"text": "Friends today we are in Pindi this shop is famous ok"},
                                   "ig_2.mp4": {"text": ROMAN[1]}})
    monkeypatch.setattr(asr_check, "DATA_DIR", data)
    monkeypatch.setattr(asr_check, "SHEET", data / "sheet.csv")
    monkeypatch.setattr(asr_check, "RESULTS_DIR", tmp_path / "results")
    assert asr_check.make_sheet({"x": "x.json", "y": "y.json"}, 5, 0, None) == 2
    with pytest.raises(SystemExit):              # never overwrite a sheet with corrections
        asr_check.make_sheet({"x": "x.json", "y": "y.json"}, 5, 0, None)

    with (data / "sheet.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["reel_url"].startswith("https://www.instagram.com/reel/")
    for r in rows:
        r["reference"] = ROMAN[0] if r["file"] == "ig_1.mp4" else ROMAN[1]
    with (data / "sheet.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    text = asr_check.score("t")
    x_line = next(line for line in text.splitlines() if line.startswith("| x |"))
    assert "| 0.0 |" in x_line                    # x matches the reference exactly
    assert (tmp_path / "results" / "e4_asr_t.md").exists()
