"""
test_profile_endpoint.py
========================
Tests for GET /onboarding/profile in server.py — specifically that
per_video_profiles from Module 2's multimodal profile are attached to
rawProfile for the dashboard's per-video cards.

Calls the route function directly with temp profile files — no API keys,
no models, no HTTP client needed.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.resolve()))

import server


VIDEO = {
    "video_id": "vid_1", "hook_type": "Bold Claim", "visual_pacing": "very fast-paced",
    "shot_count": 17, "talking_head_pct": 0.84, "speech_rate_wpm": 141.5,
}


@pytest.fixture
def profile_paths(tmp_path, monkeypatch, sample_creator_profile):
    module1 = tmp_path / "creator_profile.json"
    module2 = tmp_path / "creator_profile_multimodal.json"
    module1.write_text(json.dumps(sample_creator_profile), encoding="utf-8")
    monkeypatch.setattr(server, "PROFILE_PATH", module1)
    monkeypatch.setattr(server, "MULTIMODAL_PROFILE_PATH", module2)
    return module1, module2


class TestPerVideoProfiles:

    def test_attached_from_multimodal_profile(self, profile_paths):
        _, module2 = profile_paths
        module2.write_text(json.dumps({"per_video_profiles": [VIDEO]}), encoding="utf-8")
        raw = server.get_creator_profile()["profile"]["rawProfile"]
        assert raw["per_video_profiles"] == [VIDEO]

    def test_absent_when_no_multimodal_profile(self, profile_paths):
        raw = server.get_creator_profile()["profile"]["rawProfile"]
        assert "per_video_profiles" not in raw

    def test_module1_value_not_overwritten(self, profile_paths, sample_creator_profile):
        module1, module2 = profile_paths
        own = [{**VIDEO, "video_id": "module1_vid"}]
        module1.write_text(json.dumps({**sample_creator_profile, "per_video_profiles": own}), encoding="utf-8")
        module2.write_text(json.dumps({"per_video_profiles": [VIDEO]}), encoding="utf-8")
        raw = server.get_creator_profile()["profile"]["rawProfile"]
        assert raw["per_video_profiles"] == own

    def test_module1_fields_preserved(self, profile_paths, sample_creator_profile):
        _, module2 = profile_paths
        module2.write_text(json.dumps({"per_video_profiles": [VIDEO]}), encoding="utf-8")
        profile = server.get_creator_profile()["profile"]
        assert profile["dominantHookType"] == sample_creator_profile["signature_hooks"][0]
        assert profile["rawProfile"]["dominant_tone"] == sample_creator_profile["dominant_tone"]
