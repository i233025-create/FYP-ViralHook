"""
test_multimodal_features.py
===========================
Tests for module2_multimodal_rag feature extraction utilities.

Tests scene_detector, audio_analyzer, and visual_embedder utilities
using synthetic data — no real video files, no model downloads needed.
"""

import sys
import pytest
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.resolve()))

from module2_multimodal_rag.scene_detector import interpret_pacing
from module2_multimodal_rag.audio_analyzer import (
    interpret_speech_rate,
    interpret_energy,
)
from module2_multimodal_rag.visual_embedder import mean_pool_embedding


# ── scene_detector utility tests ─────────────────────────────────────────────

class TestInterpretPacing:

    def test_very_fast_under_2s(self):
        assert interpret_pacing(1.5) == "very fast-paced"

    def test_fast_between_2_and_4(self):
        assert interpret_pacing(3.0) == "fast-paced"

    def test_moderate_between_4_and_7(self):
        assert interpret_pacing(5.5) == "moderate"

    def test_slow_between_7_and_12(self):
        assert interpret_pacing(9.0) == "slow"

    def test_very_slow_above_12(self):
        assert interpret_pacing(15.0) == "very slow / deliberate"

    def test_boundary_exactly_2(self):
        result = interpret_pacing(2.0)
        assert result in ("very fast-paced", "fast-paced")

    def test_returns_string(self):
        assert isinstance(interpret_pacing(3.0), str)


# ── audio_analyzer utility tests ─────────────────────────────────────────────

class TestInterpretSpeechRate:

    def test_very_fast_above_170(self):
        assert interpret_speech_rate(180.0) == "very fast"

    def test_fast_between_140_and_170(self):
        assert interpret_speech_rate(155.0) == "fast"

    def test_moderate_between_110_and_140(self):
        assert interpret_speech_rate(125.0) == "moderate"

    def test_slow_between_80_and_110(self):
        assert interpret_speech_rate(95.0) == "slow"

    def test_very_slow_below_80(self):
        assert interpret_speech_rate(60.0) == "very slow / deliberate"

    def test_returns_string(self):
        assert isinstance(interpret_speech_rate(120.0), str)


class TestInterpretEnergy:

    def test_highly_dynamic_above_0005(self):
        assert "dynamic" in interpret_energy(0.006).lower()

    def test_moderately_dynamic(self):
        assert "moderately" in interpret_energy(0.003).lower()

    def test_flat_below_0001(self):
        assert "flat" in interpret_energy(0.0005).lower()

    def test_returns_string(self):
        assert isinstance(interpret_energy(0.002), str)


# ── visual_embedder utility tests ─────────────────────────────────────────────

class TestMeanPoolEmbedding:

    def test_output_length_matches_input_dim(self):
        embeddings = np.random.randn(10, 512).astype(np.float32)
        result = mean_pool_embedding(embeddings)
        assert len(result) == 512

    def test_output_is_list(self):
        embeddings = np.random.randn(5, 512).astype(np.float32)
        result = mean_pool_embedding(embeddings)
        assert isinstance(result, list)

    def test_output_is_l2_normalized(self):
        embeddings = np.random.randn(8, 512).astype(np.float32)
        result = mean_pool_embedding(embeddings)
        norm = sum(x**2 for x in result) ** 0.5
        assert abs(norm - 1.0) < 1e-5   # L2 norm ≈ 1.0

    def test_single_frame_passthrough(self):
        frame = np.ones((1, 512), dtype=np.float32)
        result = mean_pool_embedding(frame)
        norm = sum(x**2 for x in result) ** 0.5
        assert abs(norm - 1.0) < 1e-5

    def test_all_zeros_handled(self):
        embeddings = np.zeros((5, 512), dtype=np.float32)
        result = mean_pool_embedding(embeddings)
        assert len(result) == 512
        assert all(x == 0.0 for x in result)

    def test_output_elements_are_floats(self):
        embeddings = np.random.randn(3, 512).astype(np.float32)
        result = mean_pool_embedding(embeddings)
        assert all(isinstance(x, float) for x in result)


# ── Integration test (skipped in CI) ─────────────────────────────────────────

@pytest.mark.integration
def test_extract_shot_features_on_real_video():
    """
    Runs actual PySceneDetect on a real video.
    Requires a video file at module1/input_videos/.
    Skipped in CI (no videos available).
    """
    from module2_multimodal_rag.scene_detector import extract_shot_features

    input_dir = Path(__file__).parent.parent.parent / "module1_style_extraction" / "input_videos"
    videos    = list(input_dir.glob("*.mp4"))

    if not videos:
        pytest.skip("No videos in input_videos/ — skipping shot detection test")

    result = extract_shot_features(str(videos[0]))
    assert "shot_count"        in result
    assert "avg_shot_duration" in result
    assert "cut_frequency"     in result
    assert result["shot_count"] >= 1
    assert result["avg_shot_duration"] > 0
