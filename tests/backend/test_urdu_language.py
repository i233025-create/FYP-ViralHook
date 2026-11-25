"""
Urdu niches: Urdu-script and Roman Urdu titles are kept, Arabic and Hindi
are not; Urdu runs search Urdu queries and embed with the multilingual model.
No network, no model download (embeddings are faked).
"""
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

import pipeline.agents.research_agent as ra
from pipeline.local_llm import LocalLLMError

NOW = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)
UR = ("en", "ur")


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    def fail(*a, **k):
        raise LocalLLMError("no LLM (test)")
    monkeypatch.setattr(ra, "chat_json", fail)
    monkeypatch.setattr(ra, "SNAPSHOT_DIR", tmp_path / "snapshots")
    monkeypatch.setattr(ra, "_fetch_view_counts", lambda ids, key: {})
    monkeypatch.setattr(ra, "REQUIRE_MEASURED_GROWTH", False)


def _video(title, channel="Some Channel", lang="", tags=()):
    return {"video_id": "v", "title": title, "tags": list(tags), "duration_s": 40,
            "views": 5000, "subscribers": 1000, "language": lang, "channel": channel}


@pytest.mark.parametrize("title,expected", [
    ("زندگی بدل دینے والی باتیں #motivation", "ur"),
    ("Best motivation زندگی کی سچائی quotes", "ur"),          # mixed English + Urdu
    ("آپ کی زندگی بدل جائے گی", "ur"),                          # آ and ئ are Urdu too
    ("الحمد لله رب العالمين دعاء جميل", "other"),               # Arabic
    ("كيف تكون ناجحا في الحياة", "other"),                      # Arabic
    ("Zindagi badal degi ye baat suno", "roman_ur"),
    ("Gym shuru karne se pehle ye 5 baatein", "roman_ur"),
    ("Creatine Kab Lena Chahiye?", "roman_ur"),
    ("Chicken karahi recipe ghar pe asaan tareeqa", "roman_ur"),
    ("Jeevan ki sachai suvichar", "other"),                     # Roman Hindi
    ("premanand maharaj ji motivational speech", "other"),      # Hindi devotional
    ("Motivation नहीं, Discipline आपको सफल बनाएगा", "other"),    # Devanagari
    ("Jeevitha satyalu Manchi matalu", "other"),                # Telugu
    ("Powerful life lessons for success", "en"),
    ("Do this in the morning to be more productive", "en"),     # 'do', 'in', 'the' ≠ Roman Urdu
    ("Is this the best phone of the year?", "en"),
    ("Me and my dad do this every day", "en"),
])
def test_title_language(title, expected):
    assert ra.title_language(title) == expected


def test_english_niche_still_drops_urdu():
    for t in ("زندگی بدل دینے والی باتیں", "Zindagi badal degi ye baat suno"):
        assert not ra._is_usable(_video(t))
    assert ra._is_usable(_video("Powerful life lessons for success"))


@pytest.mark.parametrize("title", [
    "زندگی بدل دینے والی باتیں #motivation",
    "Zindagi badal degi ye baat suno",
    "Powerful life lessons for success",
    "Powerful life lessons in Urdu",            # naming Urdu is fine in an Urdu niche
])
def test_urdu_niche_keeps_urdu_and_english(title):
    assert ra._is_usable(_video(title), UR)


@pytest.mark.parametrize("video", [
    _video("الحمد لله رب العالمين دعاء جميل"),
    _video("Jeevan ki sachai suvichar"),
    _video("Powerful life lessons in Hindi"),
    _video("Powerful life lessons for success", lang="hi"),
    _video("Powerful life lessons for success", channel="తెలుగు ఛానల్"),
])
def test_urdu_niche_still_drops_arabic_and_hindi(video):
    assert not ra._is_usable(video, UR)


def test_urdu_language_tag_and_channel_are_accepted():
    assert ra._is_usable(_video("Zindagi badal degi ye baat suno", lang="ur"), UR)
    assert ra._is_usable(_video("زندگی بدل دینے والی باتیں", channel="اردو چینل"), UR)
    assert not ra._is_usable(_video("Zindagi badal degi ye baat suno", lang="ur"))


def test_embed_routes_urdu_niches_to_multilingual_model(monkeypatch):
    seen = []
    monkeypatch.setattr(ra, "embed_texts",
                        lambda texts, model_name="en-model": seen.append(model_name) or np.ones((len(texts), 3)))
    ra._embed(["a"], multilingual=False)
    ra._embed(["a"], multilingual=True)
    assert seen == ["en-model", ra.MULTILINGUAL_EMBEDDING_MODEL]


def _yt(vid, title, channel, hours):
    return {
        "video_id": vid, "title": title, "description": "", "tags": [], "channel": channel,
        "channel_id": channel, "language": "", "title_language": ra.title_language(title),
        "published_at": (NOW - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_s": 40, "views": 60_000, "likes": 3000, "comments": 20, "subscribers": 10_000,
        "platform": "youtube", "url": f"https://www.youtube.com/shorts/{vid}",
    }


def test_run_research_urdu_niche_end_to_end(monkeypatch, sample_creator_profile):
    videos = [_yt("u1", "Kamyabi ka raaz mehnat hai", "c1", 10),
              _yt("u2", "Kamyabi ka asal raaz mehnat hai", "c2", 20),
              _yt("u3", "کامیابی کا راز محنت ہے", "c3", 30),
              _yt("e1", "Easy chicken pasta recipe", "c4", 40),
              _yt("e2", "Quick chicken pasta recipe", "c5", 50)]
    calls = {}

    def fake_collect(queries, key, now, languages=("en",), queries_ur=None):
        calls.update(languages=languages, queries_ur=queries_ur)
        return [dict(v) for v in videos]

    models = []

    def fake_embed(texts, model_name="en-model"):
        models.append(model_name)
        rows = np.zeros((len(texts), 8))
        for i, t in enumerate(texts):
            rows[i, 0 if ("raaz" in t.lower() or "راز" in t or "growth" in t.lower()) else 1] = 1.0
            rows[i, 2 + i % 6] = 0.4      # distinct enough not to count as reuploads
        return rows / np.linalg.norm(rows, axis=1, keepdims=True)

    monkeypatch.setattr(ra, "collect_videos", fake_collect)
    monkeypatch.setattr(ra, "embed_texts", fake_embed)
    monkeypatch.setattr(ra, "MULTILINGUAL_MIN_CREATOR_FIT", 0.0)
    result = ra.run_research(sample_creator_profile, "Personal growth", now=NOW, api_key="k",
                             queries=["q"], languages=["en", "ur"], queries_ur=["kamyabi"])
    assert result["error"] is None, result["error"]
    assert calls == {"languages": ("en", "ur"), "queries_ur": ["kamyabi"]}
    assert set(models) == {ra.MULTILINGUAL_EMBEDDING_MODEL}
    assert result["stats"]["posts_by_language"] == {"en": 2, "ur": 1, "roman_ur": 2}
    assert any(t["channel_count"] == 3 for t in result["trends"])   # Urdu script + Roman Urdu together


@pytest.mark.parametrize("title", [
    "Shahi Tukray Recipe | Dawat Ki Jaan Shahi Tukray Banane Ka Sabse Aasan",
    "Kadwi Hai Magar Sach Hai Ye Baatein! | Zindagi Ki Seekh",
])
def test_roman_urdu_with_names_and_dishes(title):
    assert ra.title_language(title) == "roman_ur"


def test_hi_tag_is_accepted_only_for_urdu_titles_in_urdu_niches():
    roman = _video("Kadwi Hai Magar Sach Hai Ye Baatein", lang="hi")
    english = _video("Powerful life lessons for success", lang="hi")
    hindi = _video("Shri Krishna Ke Yeh Char Baatein Sunlo", lang="hi")
    assert ra._is_usable(roman, UR)
    assert not ra._is_usable(english, UR)
    assert not ra._is_usable(hindi, UR)
    assert not ra._is_usable(roman)                     # English niche: unchanged
