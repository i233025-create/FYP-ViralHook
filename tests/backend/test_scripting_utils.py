"""
test_scripting_utils.py
=======================
Tests for pure utility functions in server.py and pipeline/agents/scripting_agent.py

Tests _parse_timecode, _scene_to_frontend, _script_to_variant,
_extract_style_params — no API keys, no models needed.
"""

import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.resolve()))


# ── Import utilities from server.py ───────────────────────────────────────────

from server import _parse_timecode, _scene_to_frontend, _script_to_variant


class TestParseTimecode:

    def test_standard_format(self):
        start, end = _parse_timecode("0:03-0:08")
        assert start == "00:03"
        assert end   == "00:08"

    def test_double_digit_minutes(self):
        start, end = _parse_timecode("1:30-1:45")
        assert start == "01:30"
        assert end   == "01:45"

    def test_em_dash_separator(self):
        start, end = _parse_timecode("0:00–0:05")
        assert start == "00:00"
        assert end   == "00:05"

    def test_invalid_returns_fallback(self):
        start, end = _parse_timecode("invalid")
        assert start == "00:00"
        assert end   == "00:05"

    def test_zero_start(self):
        start, end = _parse_timecode("0:00-0:03")
        assert start == "00:00"
        assert end   == "00:03"

    def test_padding_single_digit_minutes(self):
        start, _ = _parse_timecode("0:05-0:10")
        assert start == "00:05"


class TestSceneToFrontend:

    def test_returns_dict_with_required_keys(self):
        scene = {
            "timecode":  "0:00-0:03",
            "clip_idea": "Talking head footage",
            "caption":   "TEST CAPTION",
            "voiceover": "This is a test voiceover.",
        }
        result = _scene_to_frontend(scene, 0, 5)
        required = {"id", "startTime", "endTime", "segment", "voiceover", "caption", "shot", "visual"}
        assert required.issubset(result.keys())

    def test_timecode_parsed_correctly(self):
        scene = {"timecode": "0:08-0:15", "clip_idea": "", "caption": "", "voiceover": ""}
        result = _scene_to_frontend(scene, 2, 5)
        assert result["startTime"] == "00:08"
        assert result["endTime"]   == "00:15"

    def test_segment_hook_for_index_0(self):
        scene = {"timecode": "0:00-0:03", "clip_idea": "", "caption": "", "voiceover": ""}
        result = _scene_to_frontend(scene, 0, 5)
        assert result["segment"] == "HOOK"

    def test_segment_conclusion_for_last(self):
        scene = {"timecode": "0:22-0:27", "clip_idea": "", "caption": "", "voiceover": ""}
        result = _scene_to_frontend(scene, 4, 5)
        assert result["segment"] == "CONCLUSION"

    def test_talking_head_shot_detection(self):
        scene = {"timecode": "0:00-0:03", "clip_idea": "talking head footage", "caption": "", "voiceover": ""}
        result = _scene_to_frontend(scene, 0, 5)
        assert "talking head" in result["shot"].lower()

    def test_screen_recording_shot_detection(self):
        scene = {"timecode": "0:00-0:03", "clip_idea": "screen recording of code", "caption": "", "voiceover": ""}
        result = _scene_to_frontend(scene, 0, 5)
        assert "screen" in result["shot"].lower()

    def test_voiceover_and_caption_preserved(self):
        scene = {
            "timecode":  "0:00-0:03",
            "clip_idea": "",
            "caption":   "MY CAPTION",
            "voiceover": "My voiceover text.",
        }
        result = _scene_to_frontend(scene, 0, 5)
        assert result["caption"]   == "MY CAPTION"
        assert result["voiceover"] == "My voiceover text."


class TestExtractStyleParams:

    def test_returns_required_keys(self):
        from pipeline.agents.scripting_agent import _extract_style_params
        profile = {
            "signature_hooks":   ["Contrarian", "Bold Claim"],
            "dominant_tone":     "Inspirational",
            "avg_pacing":        "Fast-paced",
            "typical_structure": "Hook → Explanation",
            "target_audience":   "Young adults",
        }
        params = _extract_style_params(profile)
        assert "hook_type"  in params
        assert "structure"  in params
        assert "tone"       in params
        assert "pacing"     in params

    def test_picks_first_hook(self):
        from pipeline.agents.scripting_agent import _extract_style_params
        profile = {"signature_hooks": ["Contrarian", "Bold Claim"]}
        params = _extract_style_params(profile)
        assert params["hook_type"] == "Contrarian"

    def test_handles_empty_profile(self):
        from pipeline.agents.scripting_agent import _extract_style_params
        params = _extract_style_params({})
        assert isinstance(params, dict)


class TestScriptToVariant:

    def test_variant_a_label(self):
        script = {
            "concept_name": "Test Script",
            "hook_type": "Contrarian",
            "scenes": [],
        }
        result = _script_to_variant(script, "no_history", "Test Topic", None, False)
        assert result["label"] == "VARIANT A"

    def test_variant_b_label(self):
        script = {"concept_name": "Test", "hook_type": "Bold Claim", "scenes": []}
        result = _script_to_variant(script, "retrieval_only", "Test Topic", None, False)
        assert result["label"] == "VARIANT B"

    def test_variant_c_label(self):
        script = {"concept_name": "Test", "hook_type": "Story", "scenes": []}
        result = _script_to_variant(script, "full_pipeline", "Test Topic", None, False)
        assert result["label"] == "VARIANT C"

    def test_scores_clamped_0_to_100(self):
        script = {"concept_name": "Test", "hook_type": "Contrarian", "scenes": []}
        eval_scores = {
            "style_match": 999, "hook_strength": -5,
            "structure_adherence": 7, "overall": 5,
        }
        result = _script_to_variant(script, "no_history", "Test", eval_scores, False)
        assert 0 <= result["styleConsistency"]   <= 100
        assert 0 <= result["hookAlignment"]      <= 100
        assert 0 <= result["structureAlignment"] <= 100
        assert 0 <= result["overall"]            <= 100

    def test_topic_preserved(self):
        script = {"concept_name": "Test", "hook_type": "Contrarian", "scenes": []}
        result = _script_to_variant(script, "no_history", "My Topic", None, False)
        assert result["topic"] == "My Topic"

    def test_regen_flag_preserved(self):
        script = {"concept_name": "Test", "hook_type": "Contrarian", "scenes": []}
        result = _script_to_variant(script, "full_pipeline", "Topic", None, True)
        assert result["regenTriggered"] is True
