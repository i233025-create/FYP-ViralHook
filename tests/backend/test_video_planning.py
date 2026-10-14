"""
Tests for Module 4 planning logic: style plan, timeline timing, shot queries.
Pure Python — no TTS, GPU, FFmpeg or network.
"""

import pytest

from pipeline.video.shot_planner import fallback_queries, image_prompt, keywords, plan_queries
from pipeline.video.style_plan import GENERIC, plan_style
from pipeline.video.timeline import (
    MIN_SHOT_SECONDS, Timeline, VoiceClip, SceneTrack, format_mmss, layout_scenes,
    motion_for, normalize_scenes, split_shots, to_frontend,
)


@pytest.fixture
def multimodal_profile(sample_creator_profile):
    return {
        **sample_creator_profile,
        "visual_analysis": {"mean_avg_shot_duration": 1.842, "visual_pacing": "very fast-paced"},
        "audio_analysis": {"mean_speech_rate_wpm": 127.567, "mean_pause_density": 0.052,
                           "energy_label": "highly dynamic (varied energy)"},
    }


# ─── Style plan ───────────────────────────────────────────────────────────────

class TestStylePlan:
    def test_personalised_uses_measured_profile_values(self, multimodal_profile):
        style = plan_style(multimodal_profile, "personalised")
        assert style.shot_duration == pytest.approx(1.842)
        assert style.target_wpm == pytest.approx(127.6)
        assert style.zoom_strength == 0.12
        assert style.caption_style == "karaoke"
        assert style.scene_gap == pytest.approx(0.204)
        assert "visual_analysis" in style.sources["shot_duration"]

    def test_generic_ignores_profile(self, multimodal_profile):
        style = plan_style(multimodal_profile, "generic")
        assert style == GENERIC
        assert style.target_wpm is None

    def test_text_only_profile_falls_back_to_pacing_label(self, sample_creator_profile):
        style = plan_style(sample_creator_profile, "personalised")
        assert style.shot_duration == 2.5          # "Fast-paced"
        assert style.target_wpm is None
        assert "label fallback" in style.sources["shot_duration"]

    def test_values_are_clamped(self):
        style = plan_style({"visual_analysis": {"mean_avg_shot_duration": 0.2},
                            "audio_analysis": {"mean_speech_rate_wpm": 400}}, "personalised")
        assert style.shot_duration == 1.0
        assert style.target_wpm == 200.0

    def test_unknown_mode_raises(self):
        with pytest.raises(ValueError):
            plan_style({}, "cinematic")


# ─── Timeline ─────────────────────────────────────────────────────────────────

class TestNormalizeScenes:
    def test_frontend_plan_shape(self, sample_production_plan):
        scenes = normalize_scenes(sample_production_plan)
        assert len(scenes) == 5
        assert scenes[0]["segment"] == "HOOK"
        assert scenes[1]["clip_idea"] == "B-roll: news headlines montage"   # from `visual`

    def test_script_output_shape_gets_segments(self):
        script = {"scenes": [{"timecode": "0:00-0:03", "clip_idea": "a", "caption": "c", "voiceover": "one"},
                             {"timecode": "0:03-0:06", "clip_idea": "b", "caption": "c", "voiceover": "two"},
                             {"timecode": "0:06-0:09", "clip_idea": "c", "caption": "c", "voiceover": "three"}]}
        assert [s["segment"] for s in normalize_scenes(script)] == ["HOOK", "BODY", "CONCLUSION"]

    def test_pydantic_script_output(self):
        from pipeline.state import SceneOutput, ScriptOutput
        script = ScriptOutput(script_id=1, concept_name="x", hook_type="Bold Claim", scenes=[
            SceneOutput(timecode="0:00-0:03", clip_idea="city", caption="Hi", voiceover="Hello there")])
        assert normalize_scenes(script)[0]["voiceover"] == "Hello there"

    def test_scenes_without_voiceover_are_dropped(self):
        assert len(normalize_scenes([{"voiceover": ""}, {"voiceover": "x", "visual": "v"}])) == 1

    def test_empty_script_raises(self):
        with pytest.raises(ValueError):
            normalize_scenes({"scenes": []})


class TestTiming:
    def test_layout_is_audio_first_and_contiguous(self):
        windows = layout_scenes([2.0, 3.5, 1.0], gap=0.2)
        assert windows[0] == (0.0, 2.2)
        assert windows[1] == (2.2, 5.9)
        assert windows[2][0] == 5.9
        assert windows[2][1] == pytest.approx(5.9 + 1.0 + 0.5)   # tail, not gap

    def test_split_shots_follows_creator_rhythm(self):
        shots = split_shots(0.0, 5.5, shot_duration=1.84)
        assert len(shots) == 3
        assert shots[0][0] == 0.0 and shots[-1][1] == 5.5
        assert all(e > s for s, e in shots)

    def test_split_shots_respects_min_shot(self):
        shots = split_shots(0.0, 1.5, shot_duration=0.1)
        assert all(e - s >= MIN_SHOT_SECONDS for s, e in shots)

    def test_split_shots_single_long_take(self):
        assert split_shots(2.0, 4.0, shot_duration=8.0) == [(2.0, 4.0)]

    def test_motion_cycles(self):
        assert motion_for(0) == "zoom_in" and motion_for(4) == "zoom_in"
        assert motion_for(1) != motion_for(0)

    def test_format_mmss(self):
        assert format_mmss(65.4) == "01:05"


class TestTimelineModel:
    def _timeline(self):
        voice = VoiceClip(path="vo.wav", duration=2.0)
        scene = SceneTrack(scene_id=1, segment="HOOK", start=0.0, end=2.5, clip_idea="city",
                           caption="HI", voiceover="hello", voice=voice)
        return Timeline(job_id="j1", style=GENERIC, scenes=[scene])

    def test_round_trip(self, tmp_path):
        tl = self._timeline()
        loaded = Timeline.load(tl.save(tmp_path / "timeline.json"))
        assert loaded == tl
        assert loaded.duration == 2.5

    def test_frontend_shape(self):
        row = to_frontend(self._timeline())[0]
        assert row["id"] == "s1" and row["startTime"] == "00:00" and row["visual"] == "city"


# ─── Shot planner ─────────────────────────────────────────────────────────────

class TestShotPlanner:
    def test_keywords_strip_stopwords_and_prefix(self):
        assert keywords("B-roll: a developer coding with an AI assistant") == ["developer", "coding", "assistant"]

    def test_fallback_gives_n_distinct_queries(self):
        queries = fallback_queries("crowded city street at night with neon billboards", "", 4)
        assert len(queries) == 4
        assert len(set(queries)) == 4

    def test_fallback_uses_voiceover_when_idea_empty(self):
        assert "discipline" in fallback_queries("", "Discipline beats motivation", 1)[0]

    def test_plan_queries_falls_back_when_llm_fails(self, monkeypatch):
        import pipeline.video.shot_planner as sp

        def boom(*a, **k):
            raise RuntimeError("ollama down")
        monkeypatch.setattr(sp, "llm_queries", boom)
        queries, source = plan_queries("sunrise mountain run", "go", 2)
        assert source == "keywords" and len(queries) == 2

    def test_plan_queries_uses_llm(self, monkeypatch):
        import pipeline.local_llm as llm
        monkeypatch.setattr(llm, "chat_json", lambda *a, **k: {"queries": ["man running", "sunrise peak"]})
        queries, source = plan_queries("idea", "vo", 2)
        assert source == "llm" and queries == ["man running", "sunrise peak"]

    def test_image_prompt_contains_query_and_style(self):
        prompt = image_prompt("woman running", "sunrise on a mountain trail")
        assert prompt.startswith("woman running") and "cinematic" in prompt
        assert "text" not in prompt
