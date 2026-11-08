"""E1 v2: distractor library, topic queries, topic sheet — no models needed."""

import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from make_topic_sheet import build_rows, write_sheet
from metrics import correct_ranks
from run_e1 import load_creator

LONG = "this transcript has more than enough words to count as real speech here"


def _creator(tmp_path, captions, transcripts, topics=None):
    d = tmp_path / "c"
    d.mkdir()
    with (d / "captions.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["file", "caption"])
        w.writerows(captions.items())
    (d / "transcripts.json").write_text(json.dumps({k: {"text": v} for k, v in transcripts.items()}), encoding="utf-8")
    if topics is not None:
        with (d / "topics.csv").open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["file", "transcript_preview", "topic"])
            w.writerows((k, "...", v) for k, v in topics.items())
    return d


def test_correct_ranks_with_targets_off_diagonal():
    scores = np.array([[0.1, 0.9, 0.5],    # target 1 -> rank 1
                       [0.8, 0.2, 0.3]])   # target 2 -> rank 2
    assert correct_ranks(scores, [1, 2]).tolist() == [1, 2]


def test_bad_caption_reels_stay_as_distractors(tmp_path):
    d = _creator(tmp_path,
                 {"a.mp4": "Chapli kabab in Peshawar tonight", "b.mp4": "", "c.mp4": "Who knew?", "d.mp4": "x"},
                 {"a.mp4": LONG + " a", "b.mp4": LONG + " b", "c.mp4": LONG + " c", "d.mp4": "too short"})
    data, stats = load_creator(d)
    assert [x["file"] for x in data["library"]] == ["a.mp4", "b.mp4", "c.mp4"]   # d: no speech
    assert [(q["file"], q["target"]) for q in data["queries"]] == [("a.mp4", 0)]
    assert stats["library_size"] == 3 and stats["queries"] == 1 and stats["reels_listed"] == 4

    v1, _ = load_creator(d, library_mode="queryable")                           # old behaviour
    assert [x["file"] for x in v1["library"]] == ["a.mp4"]
    assert v1["queries"][0]["target"] == 0


def test_topic_queries_ignore_captions(tmp_path):
    d = _creator(tmp_path, {"a.mp4": "", "b.mp4": "A perfectly fine caption here"},
                 {"a.mp4": LONG, "b.mp4": LONG + " b"},
                 topics={"a.mp4": "Review of the famous Sahiwal kulfi", "b.mp4": ""})
    data, stats = load_creator(d, query_source="topic")
    assert [(q["file"], q["query"], q["target"]) for q in data["queries"]] == \
        [("a.mp4", "Review of the famous Sahiwal kulfi", 0)]
    assert stats["not_query"] == {"no topic written": 1}


def test_topic_sheet_keeps_existing_topics(tmp_path):
    d = _creator(tmp_path, {"a.mp4": "", "b.mp4": "", "c.mp4": ""},
                 {"a.mp4": LONG, "b.mp4": LONG, "c.mp4": "short"},
                 topics={"a.mp4": "Already written topic here"})
    rows = build_rows(d)
    assert [(r["file"], r["topic"]) for r in rows] == [("a.mp4", "Already written topic here"), ("b.mp4", "")]
    write_sheet(d, rows)
    assert len(build_rows(d)) == 2
