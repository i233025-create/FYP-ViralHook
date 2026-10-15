"""
Tests for Module 4 rendering, assets, TTS calibration, evaluation and the
agent end-to-end. The end-to-end test needs FFmpeg (skipped otherwise) but
never a model: a fake TTS writes tones and assets fall back to placeholders.
"""

import math
import struct
import wave
from pathlib import Path

import numpy as np
import pytest

from pipeline.video import renderer
from pipeline.video.assets import AssetResolver, pick_video_file
from pipeline.video.creator_visual import CreatorVisual
from pipeline.video.evaluator import compare, evaluate, frame_scores, ratio_similarity
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


def vec(text_score, creator_score=0.0):
    """4-dim unit vector: axis 0 = the query text, axis 2 = the creator look."""
    v = np.array([text_score, 0.0, creator_score, 0.0], dtype=np.float32)
    v[1] = np.sqrt(max(0.0, 1.0 - float(v @ v)))
    return v


class FakeScorer:
    """CLIP stand-in: images keyed by file stem; every text embeds to axis 0."""

    def __init__(self, images=None):
        self.images = images or {}

    def image_embeddings(self, paths):
        return np.stack([self.images[Path(p).stem] for p in paths])

    def text_embeddings(self, texts):
        return np.tile(np.eye(4, dtype=np.float32)[0], (len(texts), 1))


CREATOR = CreatorVisual(vectors=np.array([[0, 0, 1, 0], [0, 0.2, 0.98, 0]], dtype=np.float32))


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

    def _pexels(self, tmp_path, monkeypatch, images, **kwargs):
        resolver = AssetResolver(tmp_path, pexels_key="k", scorer=FakeScorer(images),
                                 use_image_gen=False, **kwargs)
        files = [{"file_type": "video/mp4", "width": 1080, "height": 1920, "link": "l"}]
        videos = [{"id": int(k), "image": "u", "video_files": files} for k in images]
        monkeypatch.setattr(resolver.pexels, "search", lambda q: videos)
        monkeypatch.setattr(resolver.pexels, "thumbnail", lambda v: tmp_path / f"{v['id']}.jpg")
        monkeypatch.setattr(resolver.pexels, "download", lambda v: tmp_path / f"{v['id']}.mp4")
        return resolver

    def test_pexels_below_threshold_falls_through(self, tmp_path, monkeypatch):
        resolver = self._pexels(tmp_path, monkeypatch, {"7": vec(0.1)})
        assert resolver.resolve("q").source == "placeholder"

    def test_pexels_best_unused_clip_wins(self, tmp_path, monkeypatch):
        resolver = self._pexels(tmp_path, monkeypatch, {"1": vec(0.30), "2": vec(0.35)})
        used = set()
        first = resolver.resolve("q", used_ids=used)
        assert first.source == "pexels" and first.source_id == "2" and first.clip_score == 0.35
        second = resolver.resolve("q", used_ids=used)
        assert second.source_id == "1"                # clip 2 already used

    def test_creator_weight_reorders_on_topic_clips(self, tmp_path, monkeypatch):
        images = {"1": vec(0.30, creator_score=0.9), "2": vec(0.33)}
        resolver = self._pexels(tmp_path, monkeypatch, images)
        assert resolver.resolve("q", creator=CREATOR, creator_weight=0.0).source_id == "2"
        personal = resolver.resolve("q", creator=CREATOR, creator_weight=0.5)
        assert personal.source_id == "1"
        assert personal.creator_score > 0.8

    def test_creator_weight_never_admits_off_topic_clip(self, tmp_path, monkeypatch):
        images = {"1": vec(0.10, creator_score=0.99), "2": vec(0.26)}
        resolver = self._pexels(tmp_path, monkeypatch, images)
        assert resolver.resolve("q", creator=CREATOR, creator_weight=5.0).source_id == "2"

    def test_image_gen_retries_once_after_freeing_gpu(self, tmp_path, monkeypatch):
        class FlakyGen:
            calls = 0

            def generate(self, prompt, path, seed=None):
                FlakyGen.calls += 1
                if FlakyGen.calls == 1:
                    raise RuntimeError("CUDA out of memory")
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                Path(path).write_bytes(b"png")

        resolver = AssetResolver(tmp_path, pexels_key="", scorer=FakeScorer(), image_gen=FlakyGen(),
                                 use_image_gen=True, image_candidates=1)
        freed = []
        monkeypatch.setattr(resolver, "_free_gpu", lambda: freed.append(True))
        assert resolver.resolve("q", "prompt").source == "sdxl"   # not a placeholder
        assert freed == [True]
        assert resolver.resolve("q2", "prompt 2").source == "sdxl"   # image gen still on

    def test_image_gen_gives_up_after_second_failure(self, tmp_path, monkeypatch):
        class BrokenGen:
            def generate(self, prompt, path, seed=None):
                raise RuntimeError("CUDA out of memory")

        resolver = AssetResolver(tmp_path, pexels_key="", scorer=FakeScorer(), image_gen=BrokenGen(),
                                 use_image_gen=True, image_candidates=1)
        monkeypatch.setattr(resolver, "_free_gpu", lambda: None)
        assert resolver.resolve("q", "prompt").source == "placeholder"
        assert resolver.use_image_gen is False

    def test_image_candidates_ranked_same_count_both_modes(self, tmp_path):
        scorer = FakeScorer()

        class FakeGen:
            calls = 0

            def generate(self, prompt, path, seed=None):
                FakeGen.calls += 1
                # even seed: on-topic; odd seed: creator-looking but a bit less on-topic
                scorer.images[Path(path).stem] = vec(0.32) if seed % 2 == 0 else vec(0.29, 0.9)
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                Path(path).write_bytes(b"png")

        def resolver(cache):
            return AssetResolver(tmp_path / cache, pexels_key="", scorer=scorer, image_gen=FakeGen(),
                                 use_image_gen=True, image_candidates=2)

        generic = resolver("g").resolve("q", "prompt", creator=CREATOR, creator_weight=0.0)
        personal = resolver("p").resolve("q", "prompt", creator=CREATOR, creator_weight=0.5)
        assert FakeGen.calls == 4                                     # 2 candidates each
        assert generic.clip_score > personal.clip_score
        assert personal.creator_score > generic.creator_score
        assert "best of 2" in personal.note


# ─── Creator visual ───────────────────────────────────────────────────────────

class TestCreatorVisual:
    def test_load_snapshot(self, tmp_path):
        import json
        snap = tmp_path / "snap.json"
        snap.write_text(json.dumps({"points": [
            {"visual_vector": [0, 0, 2, 0], "payload": {"talking_head_pct": 0.8}},
            {"visual_vector": [0, 1, 1, 0], "payload": {"talking_head_pct": 0.6}},
            {"visual_vector": [0, 0, 0, 0], "payload": {}},               # failed video, skipped
        ]}))
        from pipeline.video.creator_visual import load_creator_visual
        creator = load_creator_visual(snap)
        assert creator.vectors.shape == (2, 4)
        assert np.allclose(np.linalg.norm(creator.vectors, axis=1), 1)
        assert creator.talking_head_pct == 0.7

    def test_missing_snapshot_is_none(self, tmp_path):
        from pipeline.video.creator_visual import load_creator_visual
        assert load_creator_visual(tmp_path / "nope.json") is None

    def test_similarity_and_self_similarity(self):
        assert CREATOR.similarity(np.eye(4, dtype=np.float32)[2])[0] > 0.99
        assert 0.9 < CREATOR.self_similarity() <= 1.0
        assert CreatorVisual(vectors=CREATOR.vectors[:1]).self_similarity() is None

    def test_describe_look_picks_one_word_per_group(self):
        from pipeline.video.creator_visual import LOOK_VOCAB, describe_look

        class LookScorer:
            def text_embeddings(self, texts):
                # the creator axis (2) lights up for "warm" and "city"
                return np.stack([np.eye(4, dtype=np.float32)[2 if ("warm" in t or "city" in t) else 0]
                                 for t in texts])

        look = describe_look(CREATOR, LookScorer())
        assert len(look) == len(LOOK_VOCAB)
        assert "warm golden light" in look and "city street" in look


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

    def test_frame_scores_visual_match(self, tmp_path):
        scorer = FakeScorer({"a": vec(0.3, 0.9), "b": vec(0.25, 0.85)})
        frames = [(str(tmp_path / "a.jpg"), "idea one"), (str(tmp_path / "b.jpg"), "idea two")]
        alignment, visual = frame_scores(frames, scorer, CREATOR)
        assert alignment["mean"] == pytest.approx(0.275, abs=1e-3)
        assert 0.8 < visual["creator_similarity"] < 1.0
        assert visual["creator_self_similarity"] == CREATOR.self_similarity()

    def test_visual_match_joins_style_fidelity(self, tmp_path, monkeypatch):
        import pipeline.video.evaluator as ev
        monkeypatch.setattr(ev, "extract_midframes",
                            lambda *a: [(str(tmp_path / "a.jpg"), "city")])
        profile = {"visual_analysis": {"mean_avg_shot_duration": 2.0},
                   "audio_analysis": {"mean_speech_rate_wpm": 120}}
        result = evaluate("v.mp4", _timeline(), profile, tmp_path,
                          measure=lambda v, t: {"avg_shot_duration": 2.0, "speech_rate_wpm": 120},
                          scorer=FakeScorer({"a": vec(0.3, 0.5)}), creator=CREATOR)
        vm = result["scores"]["visual_match"]
        assert 0 < vm < 1
        assert result["scores"]["style_fidelity"] == pytest.approx((1 + 1 + vm) / 3, abs=1e-3)

    def test_compare_deltas(self):
        p = {"scores": {"pacing_match": 0.9, "speech_rate_match": 0.8, "style_fidelity": 0.85}}
        g = {"scores": {"pacing_match": 0.3, "speech_rate_match": 0.7, "style_fidelity": 0.5}}
        assert compare(p, g)["style_fidelity"]["delta"] == 0.35


class _NoClip(FakeScorer):
    pass


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
                            use_llm=False, run_evaluation=False, creator=None,
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
