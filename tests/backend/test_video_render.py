"""
Tests for Module 4 rendering, assets, TTS calibration, evaluation and the
agent end-to-end. The end-to-end test needs FFmpeg (skipped otherwise) but
never a model: a fake TTS writes tones and assets fall back to placeholders.
"""

import math
import struct
import wave
from pathlib import Path

import pytest

from pipeline.video import renderer
from pipeline.video.assets import AssetResolver, pick_video_file
from pipeline.video.evaluator import compare, evaluate, ratio_similarity
from pipeline.video.style_plan import GENERIC, plan_style
from pipeline.video.timeline import Asset, SceneTrack, Shot, Timeline, VoiceClip, WordTiming
from pipeline.video.tts import estimate_word_timings, synthesize_scene, words_per_minute

needs_ffmpeg = pytest.mark.skipif(not renderer.ffmpeg_available(), reason="ffmpeg not installed")


class FakeTTS:
    """Writes a tone whose length is proportional to word count and 1/speed."""

    def __init__(self, seconds_per_word=0.4):
        self.seconds_per_word = seconds_per_word
        self.calls = []

    def synthesize(self, text, out_path, speed=1.0):
        self.calls.append(speed)
        duration = round(len(text.split()) * self.seconds_per_word / speed, 3)
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        rate = 24000
        with wave.open(str(out_path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(b"".join(struct.pack("<h", int(3000 * math.sin(i / 20)))
                                   for i in range(int(duration * rate))))
        return VoiceClip(path=str(out_path), duration=duration, speed=speed)


def _timeline(caption_style="karaoke"):
    style = GENERIC.model_copy(update={"caption_style": caption_style})
    words = [WordTiming(word=w, start=i * 0.4, end=i * 0.4 + 0.35)
             for i, w in enumerate("Stop chasing motivation. Build {discipline} instead".split())]
    voice = VoiceClip(path="vo.wav", duration=2.4, words=words)
    asset = Asset(path="a.png", kind="image", source="placeholder", query="q")
    scene = SceneTrack(scene_id=1, segment="HOOK", start=0.0, end=2.9, clip_idea="city",
                       caption="STOP CHASING", voiceover="Stop chasing motivation.", voice=voice,
                       shots=[Shot(start=0.0, end=1.45, query="q", motion="zoom_in", asset=asset),
                              Shot(start=1.45, end=2.9, query="q", motion="pan_left", asset=asset)])
    return Timeline(job_id="t", style=style, scenes=[scene])


# ─── TTS calibration ──────────────────────────────────────────────────────────

class TestTTSCalibration:
    def test_estimate_word_timings_cover_duration(self):
        timings = estimate_word_timings("one two three", 3.0)
        assert timings[0].start == 0.0 and timings[-1].end == pytest.approx(3.0)

    def test_wpm(self):
        assert words_per_minute("a b c d", 2.0) == 120.0

    def test_resynthesizes_to_hit_target(self, tmp_path):
        tts = FakeTTS(seconds_per_word=0.4)          # 150 wpm at speed 1
        clip = synthesize_scene(tts, "word " * 10, str(tmp_path / "v.wav"), target_wpm=120)
        assert tts.calls == [1.0, 0.8]
        assert clip.measured_wpm == pytest.approx(120, abs=1)
        assert clip.words                             # estimated when engine gives none

    def test_no_target_keeps_default_speed(self, tmp_path):
        tts = FakeTTS()
        synthesize_scene(tts, "a b c", str(tmp_path / "v.wav"), target_wpm=None)
        assert tts.calls == [1.0]

    def test_close_enough_skips_second_pass(self, tmp_path):
        tts = FakeTTS(seconds_per_word=0.4)
        synthesize_scene(tts, "word " * 10, str(tmp_path / "v.wav"), target_wpm=152)
        assert tts.calls == [1.0]


# ─── Captions + FFmpeg commands ───────────────────────────────────────────────

class TestRendererPieces:
    def test_ass_time(self):
        assert renderer.ass_time(3661.256) == "1:01:01.26"

    def test_ass_escape_removes_override_braces(self):
        assert renderer.ass_escape("a {b}\\c") == "a (b)/c"

    def test_chunks_break_on_punctuation(self):
        words = _timeline().scenes[0].voice.words
        chunks = renderer.chunk_words(words)
        assert [w.word for w in chunks[0]] == ["Stop", "chasing", "motivation."]

    def test_karaoke_highlights_each_word(self):
        ass = renderer.build_ass(_timeline("karaoke"))
        events = [ln for ln in ass.splitlines() if ln.startswith("Dialogue")]
        assert len(events) == 6
        assert renderer.HIGHLIGHT in events[0] and "STOP" in events[0]
        assert "{DISCIPLINE}" not in ass and "(DISCIPLINE)" in ass

    def test_scene_captions_one_per_scene(self):
        events = [ln for ln in renderer.build_ass(_timeline("scene")).splitlines() if ln.startswith("Dialogue")]
        assert len(events) == 1 and "STOP CHASING" in events[0]

    def test_frame_count_has_no_drift(self):
        bounds = [0.0, 1.234, 2.468, 3.702]
        total = sum(renderer.frame_count(a, b, 30) for a, b in zip(bounds, bounds[1:]))
        assert total == round(3.702 * 30)

    def test_image_shot_uses_zoompan(self):
        tl = _timeline()
        cmd = renderer.shot_command(tl.scenes[0].shots[0], "out.mp4", tl)
        vf = cmd[cmd.index("-vf") + 1]
        assert "zoompan" in vf and "s=1080x1920" in vf
        assert cmd[cmd.index("-frames:v") + 1] == str(round(1.45 * 30))

    def test_video_shot_loops_and_crops(self):
        tl = _timeline()
        shot = tl.scenes[0].shots[0].model_copy(update={"asset": Asset(
            path="c.mp4", kind="video", source="pexels", query="q")})
        cmd = renderer.shot_command(shot, "out.mp4", tl)
        assert "-stream_loop" in cmd and "crop=1080:1920" in cmd[cmd.index("-vf") + 1]

    def test_audio_command_places_voice_at_scene_start(self):
        tl = _timeline()
        second = tl.scenes[0].model_copy(update={"scene_id": 2, "start": 2.9, "end": 5.0})
        tl = tl.model_copy(update={"scenes": [tl.scenes[0], second]})
        cmd = renderer.audio_command(tl, "out.wav")
        graph = cmd[cmd.index("-filter_complex") + 1]
        assert "adelay=2900|2900" in graph and "atrim=0:5.0" in graph

    def test_audio_command_ducks_music(self):
        cmd = renderer.audio_command(_timeline(), "out.wav", music="m.mp3")
        graph = cmd[cmd.index("-filter_complex") + 1]
        assert "sidechaincompress" in graph


# ─── Assets ───────────────────────────────────────────────────────────────────

class TestAssets:
    def test_pick_video_file_prefers_smallest_portrait_hd(self):
        video = {"video_files": [
            {"file_type": "video/mp4", "width": 1920, "height": 1080, "link": "landscape"},
            {"file_type": "video/mp4", "width": 540, "height": 960, "link": "too-small"},
            {"file_type": "video/mp4", "width": 1440, "height": 2560, "link": "big"},
            {"file_type": "video/mp4", "width": 1080, "height": 1920, "link": "best"},
        ]}
        assert pick_video_file(video)["link"] == "best"

    def test_pick_video_file_none(self):
        assert pick_video_file({"video_files": []}) is None

    def test_placeholder_when_nothing_else(self, tmp_path):
        resolver = AssetResolver(tmp_path, pexels_key="", use_image_gen=False)
        asset = resolver.resolve("city at night")
        assert asset.source == "placeholder" and Path(asset.path).exists()

    def test_pexels_below_threshold_falls_through(self, tmp_path, monkeypatch):
        class Scorer:
            def score(self, paths, text):
                return [0.1] * len(paths)

        resolver = AssetResolver(tmp_path, pexels_key="k", scorer=Scorer(), use_image_gen=False)
        video = {"id": 7, "image": "u", "video_files": [
            {"file_type": "video/mp4", "width": 1080, "height": 1920, "link": "l"}]}
        monkeypatch.setattr(resolver.pexels, "search", lambda q: [video])
        monkeypatch.setattr(resolver.pexels, "thumbnail", lambda v: tmp_path / "t.jpg")
        assert resolver.resolve("q").source == "placeholder"

    def test_pexels_best_unused_clip_wins(self, tmp_path, monkeypatch):
        class Scorer:
            def score(self, paths, text):
                return [0.30, 0.35][:len(paths)]

        resolver = AssetResolver(tmp_path, pexels_key="k", scorer=Scorer(), use_image_gen=False)
        files = [{"file_type": "video/mp4", "width": 1080, "height": 1920, "link": "l"}]
        videos = [{"id": 1, "image": "u", "video_files": files}, {"id": 2, "image": "u", "video_files": files}]
        monkeypatch.setattr(resolver.pexels, "search", lambda q: videos)
        monkeypatch.setattr(resolver.pexels, "thumbnail", lambda v: tmp_path / f"{v['id']}.jpg")
        monkeypatch.setattr(resolver.pexels, "download", lambda v: tmp_path / f"{v['id']}.mp4")
        used = set()
        first = resolver.resolve("q", used_ids=used)
        assert first.source == "pexels" and first.source_id == "2" and first.clip_score == 0.35
        second = resolver.resolve("q", used_ids=used)
        assert second.source_id == "1"                # clip 2 already used


# ─── Evaluator ────────────────────────────────────────────────────────────────

class TestEvaluator:
    def test_ratio_similarity(self):
        assert ratio_similarity(2.0, 2.0) == 1.0
        assert ratio_similarity(6.0, 2.0) == 0.0
        assert ratio_similarity(1.0, 2.0) == ratio_similarity(4.0, 2.0)
        assert ratio_similarity(None, 2.0) is None

    def test_evaluate_with_injected_measurements(self, tmp_path):
        profile = {"visual_analysis": {"mean_avg_shot_duration": 1.84},
                   "audio_analysis": {"mean_speech_rate_wpm": 127.6}}
        measured = {"avg_shot_duration": 1.84, "speech_rate_wpm": 127.6}
        result = evaluate("missing.mp4", _timeline(), profile, tmp_path,
                          measure=lambda v, t: measured, scorer=_NoClip())
        assert result["scores"]["style_fidelity"] == 1.0
        assert result["asset_sources"] == {"placeholder": 2}

    def test_no_targets_gives_none(self, tmp_path):
        result = evaluate("missing.mp4", _timeline(), {}, tmp_path,
                          measure=lambda v, t: {"avg_shot_duration": 2.0}, scorer=_NoClip())
        assert result["scores"]["style_fidelity"] is None

    def test_compare_deltas(self):
        p = {"scores": {"pacing_match": 0.9, "speech_rate_match": 0.8, "style_fidelity": 0.85}}
        g = {"scores": {"pacing_match": 0.3, "speech_rate_match": 0.7, "style_fidelity": 0.5}}
        assert compare(p, g)["style_fidelity"]["delta"] == 0.35


class _NoClip:
    def score(self, paths, text):
        return [0.0 for _ in paths]


# ─── End-to-end (FFmpeg, no models) ───────────────────────────────────────────

@needs_ffmpeg
def test_generate_video_end_to_end(tmp_path, sample_production_plan):
    from pipeline.agents.video_agent import STEPS, generate_video

    profile = {"visual_analysis": {"mean_avg_shot_duration": 1.84},
               "audio_analysis": {"mean_speech_rate_wpm": 127.6, "mean_pause_density": 0.05},
               "visual_style_suggestions": ["Overlay text highlighting key phrases"]}
    plan = {**sample_production_plan, "scenes": sample_production_plan["scenes"][:2]}
    steps = []
    result = generate_video(plan, profile, out_dir=tmp_path, tts=FakeTTS(0.3),
                            resolver=AssetResolver(tmp_path / "cache", pexels_key="", use_image_gen=False),
                            use_llm=False, run_evaluation=False,
                            on_step=lambda n, label, detail: steps.append(n))

    video = Path(result["video_path"])
    assert video.exists() and video.stat().st_size > 0
    timeline = result["timeline"]
    assert timeline.style.caption_style == "karaoke"
    assert all(len(sc.shots) >= 2 for sc in timeline.scenes)           # cut every ~1.84 s
    assert timeline.scenes[1].start == timeline.scenes[0].end            # contiguous
    assert sorted(set(steps)) == list(range(1, len(STEPS)))              # 1-6 (eval off)

    import subprocess
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height",
                            "-of", "default=nw=1", str(video)], capture_output=True, text=True).stdout
    assert "width=1080" in probe and "height=1920" in probe
    duration = float([ln for ln in probe.splitlines() if ln.startswith("duration=")][0].split("=")[1])
    assert duration == pytest.approx(timeline.duration, abs=0.15)


def test_personalised_and_generic_differ(sample_creator_profile):
    profile = {**sample_creator_profile, "visual_analysis": {"mean_avg_shot_duration": 1.84}}
    assert plan_style(profile, "personalised").shot_duration != plan_style(profile, "generic").shot_duration
