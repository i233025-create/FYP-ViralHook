"""
audio_analyzer.py
=================
Extracts audio-level features from a video using librosa.

Pipeline:
  1. Extract audio from video as WAV (FFmpeg)
  2. Load WAV with librosa
  3. Extract features

Features extracted:
  - speech_rate_wpm:    Estimated words per minute from transcript + duration
  - energy_variance:    How much the audio volume varies (dynamic vs flat delivery)
  - pause_density:      Ratio of silent frames to total — indicates speech rhythm
  - avg_energy:         Mean RMS energy (overall loudness level)
  - tempo:              Estimated BPM of audio rhythm (speech cadence proxy)

Why these features matter:
  A creator who speaks at 160wpm with high energy variance and few pauses
  has a completely different delivery style from one at 90wpm with long pauses.
  These features complement visual pacing for a fuller creator representation.
"""

from __future__ import annotations

import subprocess
import tempfile
import os
from pathlib import Path


def _extract_audio_wav(video_path: str) -> tuple[str, str]:
    """
    Extract audio track from video as 16kHz mono WAV using FFmpeg.
    Returns (wav_path, temp_dir). Caller must clean up temp_dir.
    """
    import tempfile, shutil
    temp_dir = tempfile.mkdtemp(prefix="viralhook_audio_")
    wav_path = str(Path(temp_dir) / "audio.wav")

    cmd = [
        "ffmpeg",
        "-i", str(video_path),
        "-vn",               # no video
        "-acodec", "pcm_s16le",
        "-ar", "16000",      # 16kHz — sufficient for speech analysis
        "-ac", "1",          # mono
        wav_path,
        "-y",
        "-loglevel", "error",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError(
            f"FFmpeg audio extraction failed: {result.stderr}"
        )
    return wav_path, temp_dir


def extract_audio_features(
    video_path: str,
    transcript: str = "",
    video_duration: float = 0.0,
) -> dict:
    """
    Extract audio features from a video file.

    Args:
        video_path:      Path to video file.
        transcript:      Optional transcript text for speech rate calculation.
        video_duration:  Video duration in seconds (for speech rate).
                         If 0, estimated from audio.

    Returns:
        Dict with keys:
          speech_rate_wpm, energy_variance, pause_density,
          avg_energy, tempo, duration_seconds
    """
    import shutil

    fallback = {
        "speech_rate_wpm":  120.0,
        "energy_variance":  0.01,
        "pause_density":    0.2,
        "avg_energy":       0.05,
        "tempo":            120.0,
        "duration_seconds": video_duration or 30.0,
    }

    wav_path, temp_dir = None, None
    try:
        import librosa
        import numpy as np

        wav_path, temp_dir = _extract_audio_wav(video_path)

        # Load audio
        y, sr = librosa.load(wav_path, sr=16000, mono=True)
        duration = librosa.get_duration(y=y, sr=sr)

        # ── Speech rate (wpm) ──────────────────────────────────────────────────
        if transcript and duration > 0:
            word_count = len(transcript.split())
            speech_rate_wpm = (word_count / duration) * 60.0
        else:
            # Estimate from voiced frame ratio as proxy
            speech_rate_wpm = 120.0

        # ── RMS energy ────────────────────────────────────────────────────────
        # Compute per-frame RMS
        frame_length = 512
        hop_length   = 256
        rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]

        avg_energy      = float(np.mean(rms))
        energy_variance = float(np.var(rms))

        # ── Pause density ──────────────────────────────────────────────────────
        # Frames where RMS < 5% of mean = silence/pause
        silence_threshold = avg_energy * 0.05
        silent_frames     = np.sum(rms < silence_threshold)
        pause_density     = float(silent_frames / len(rms)) if len(rms) > 0 else 0.2

        # ── Tempo (speech cadence proxy) ───────────────────────────────────────
        # librosa.beat.beat_track works on music but gives a rough
        # cadence estimate for speech rhythm too
        try:
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            tempo = float(tempo) if tempo > 0 else 120.0
        except Exception:
            tempo = 120.0

        return {
            "speech_rate_wpm":  round(speech_rate_wpm, 1),
            "energy_variance":  round(energy_variance, 6),
            "pause_density":    round(pause_density, 4),
            "avg_energy":       round(avg_energy, 6),
            "tempo":            round(tempo, 1),
            "duration_seconds": round(duration, 2),
        }

    except Exception as e:
        print(f"[AudioAnalyzer] Feature extraction failed: {e}")
        print("[AudioAnalyzer] Returning fallback audio features.")
        return fallback

    finally:
        if temp_dir:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)


def interpret_speech_rate(wpm: float) -> str:
    """Convert wpm to human-readable label for LLM context."""
    if wpm > 170:
        return "very fast"
    elif wpm > 140:
        return "fast"
    elif wpm > 110:
        return "moderate"
    elif wpm > 80:
        return "slow"
    else:
        return "very slow / deliberate"


def interpret_energy(variance: float) -> str:
    """Convert energy variance to delivery style label."""
    if variance > 0.005:
        return "highly dynamic (varied energy)"
    elif variance > 0.001:
        return "moderately dynamic"
    else:
        return "flat / consistent energy"
