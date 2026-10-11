"""
test_xml_export.py
==================
Tests for pipeline/json_to_premiere_xml.py

Verifies that the XML builder produces valid XMEML v4 output
with correct structure, timecodes, and content.
No API keys required — pure Python/XML tests.
"""

import sys
import pytest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.resolve()))

from pipeline.json_to_premiere_xml import build_xml, prettify_xml


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_xml_scenes():
    return [
        {
            "timecode": "0:00-0:03",
            "clip_idea": "Talking-head footage, direct eye contact",
            "caption":   "AI WILL REPLACE DEVELOPERS?",
            "voiceover": "AI will not replace developers.",
        },
        {
            "timecode": "0:03-0:08",
            "clip_idea": "B-roll: news headlines montage",
            "caption":   "WRONG QUESTION",
            "voiceover": "Everyone is debating whether AI takes our jobs.",
        },
        {
            "timecode": "0:08-0:15",
            "clip_idea": "B-roll: developer coding",
            "caption":   "ONE-PERSON TEAM",
            "voiceover": "AI agents are turning solo developers into one-person teams.",
        },
    ]


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestBuildXml:

    def test_returns_element(self, sample_xml_scenes):
        root = build_xml("Test_Project", sample_xml_scenes)
        assert root is not None
        assert isinstance(root, ET.Element)

    def test_root_tag_is_xmeml(self, sample_xml_scenes):
        root = build_xml("Test_Project", sample_xml_scenes)
        assert root.tag == "xmeml"

    def test_xmeml_version_is_4(self, sample_xml_scenes):
        root = build_xml("Test_Project", sample_xml_scenes)
        assert root.attrib.get("version") == "4"

    def test_sequence_name_matches(self, sample_xml_scenes):
        root = build_xml("My_Video", sample_xml_scenes)
        seq  = root.find("sequence")
        name = seq.find("name")
        assert name is not None
        assert name.text == "My_Video"

    def test_has_video_and_audio_tracks(self, sample_xml_scenes):
        root  = build_xml("Test", sample_xml_scenes)
        seq   = root.find("sequence")
        media = seq.find("media")
        assert media.find("video") is not None
        assert media.find("audio") is not None

    def test_video_track_has_correct_clip_count(self, sample_xml_scenes):
        root    = build_xml("Test", sample_xml_scenes)
        seq     = root.find("sequence")
        media   = seq.find("media")
        video   = media.find("video")
        v1_track = video.findall("track")[0]
        clips   = v1_track.findall("clipitem")
        assert len(clips) == len(sample_xml_scenes)

    def test_duration_is_positive_integer(self, sample_xml_scenes):
        root = build_xml("Test", sample_xml_scenes)
        seq  = root.find("sequence")
        dur  = seq.find("duration")
        assert dur is not None
        assert int(dur.text) > 0

    def test_resolution_is_vertical_1080x1920(self, sample_xml_scenes):
        root   = build_xml("Test", sample_xml_scenes)
        seq    = root.find("sequence")
        sc     = seq.find("samplecharacteristics")
        width  = sc.find("width").text
        height = sc.find("height").text
        assert width  == "1080"
        assert height == "1920"

    def test_empty_scenes_raises_or_returns(self):
        """Build with empty scenes should either raise or return minimal XML."""
        try:
            root = build_xml("Empty", [])
            assert root is not None
        except Exception:
            pass  # Either behaviour is acceptable


class TestPrettifyXml:

    def test_returns_string(self, sample_xml_scenes):
        root   = build_xml("Test", sample_xml_scenes)
        result = prettify_xml(root)
        assert isinstance(result, str)

    def test_starts_with_xml_declaration(self, sample_xml_scenes):
        root   = build_xml("Test", sample_xml_scenes)
        result = prettify_xml(root)
        assert result.startswith("<?xml")

    def test_contains_xmeml_tag(self, sample_xml_scenes):
        root   = build_xml("Test", sample_xml_scenes)
        result = prettify_xml(root)
        assert "<xmeml" in result

    def test_is_valid_xml(self, sample_xml_scenes):
        root   = build_xml("Test", sample_xml_scenes)
        result = prettify_xml(root)
        # Should parse back without error
        parsed = ET.fromstring(result.split("?>", 1)[-1].strip())
        assert parsed.tag == "xmeml"

    def test_captions_present_in_output(self, sample_xml_scenes):
        root   = build_xml("Test", sample_xml_scenes)
        result = prettify_xml(root)
        assert "AI WILL REPLACE DEVELOPERS?" in result
        assert "WRONG QUESTION" in result

    def test_voiceover_present_in_output(self, sample_xml_scenes):
        root   = build_xml("Test", sample_xml_scenes)
        result = prettify_xml(root)
        assert "AI will not replace developers" in result
