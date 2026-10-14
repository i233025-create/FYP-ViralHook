"""
tts.py — Voiceover synthesis (Kokoro-82M, local)
=================================================
Each scene's voiceover becomes one WAV plus word-level timings, which drive
both the scene length (audio-first timeline) and the karaoke captions.

Speech-rate calibration (personalised mode):
  1. synthesize at speed 1.0 and *measure* words-per-minute from the audio
  2. speed = target_wpm / measured_wpm   (clamped 0.75–1.35)
  3. re-synthesize at that speed if it differs by more than 5 %
So the voiceover matches the creator's measured 127 wpm instead of the TTS
voice's own rate.

Word timings come from Kokoro's token timestamps. If an engine returns none,
timings are estimated by spreading words over the audio by character length.

Config (.env, optional):
  KOKORO_VOICE = af_heart    (see hexgrad/Kokoro-82M VOICES.md)
  KOKORO_LANG  = a           (a = American English, b = British)
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Protocol

from .timeline import VoiceClip, WordTiming

SAMPLE_RATE = 24000
SPEED_MIN, SPEED_MAX = 0.75, 1.35
RECALIBRATE_ABOVE = 0.05


class TTSError(RuntimeError):
    """Raised when no voiceover can be synthesized."""


class TTSEngine(Protocol):
    def synthesize(self, text: str, out_path: str, speed: float = 1.0) -> VoiceClip:
        ...


# ─── Helpers ──────────────────────────────────────────────────────────────────

def count_words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", text))


def words_per_minute(text: str, seconds: float) -> float:
    return round(count_words(text) / seconds * 60.0, 1) if seconds > 0 else 0.0


def estimate_word_timings(text: str, duration: float) -> list[WordTiming]:
    """Spread words over `duration` proportionally to their length."""
    words = text.split()
    if not words or duration <= 0:
        return []
    weights = [len(w) + 1 for w in words]
    total = sum(weights)
    timings, t = [], 0.0
    for word, weight in zip(words, weights):
        span = duration * weight / total
        timings.append(WordTiming(word=word, start=round(t, 3), end=round(t + span, 3)))
        t += span
    return timings


# ─── Kokoro ───────────────────────────────────────────────────────────────────

class KokoroTTS:
    """Kokoro-82M via the `kokoro` package. Model loads once, on first use."""

    def __init__(self, voice: str | None = None, lang: str | None = None):
        self.voice = voice or os.getenv("KOKORO_VOICE", "af_heart")
        self.lang = lang or os.getenv("KOKORO_LANG", "a")
        self._pipeline = None

    def _load(self):
        if self._pipeline is None:
            try:
                from kokoro import KPipeline
            except ImportError as e:
                raise TTSError("kokoro is not installed: pip install -r pipeline/video/requirements.txt") from e
            self._pipeline = KPipeline(lang_code=self.lang, repo_id="hexgrad/Kokoro-82M")
        return self._pipeline

    def synthesize(self, text: str, out_path: str, speed: float = 1.0) -> VoiceClip:
        import numpy as np
        import soundfile as sf

        pipeline = self._load()
        chunks, words, offset = [], [], 0.0
        for result in pipeline(text, voice=self.voice, speed=speed):
            if result.audio is None:
                continue
            audio = result.audio.detach().cpu().numpy() if hasattr(result.audio, "detach") else np.asarray(result.audio)
            for token in result.tokens or []:
                if token.start_ts is None or token.end_ts is None:
                    continue
                if not re.search(r"[A-Za-z0-9]", token.text or ""):
                    continue   # punctuation tokens carry no spoken word
                words.append(WordTiming(word=token.text,
                                        start=round(offset + token.start_ts, 3),
                                        end=round(offset + token.end_ts, 3)))
            chunks.append(audio)
            offset += len(audio) / SAMPLE_RATE

        if not chunks:
            raise TTSError(f"Kokoro produced no audio for: {text[:60]!r}")
        audio = np.concatenate(chunks)
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        sf.write(out_path, audio, SAMPLE_RATE)

        duration = round(len(audio) / SAMPLE_RATE, 3)
        return VoiceClip(path=str(out_path), duration=duration,
                         words=words or estimate_word_timings(text, duration),
                         speed=speed, measured_wpm=words_per_minute(text, duration))


# ─── Calibrated synthesis ─────────────────────────────────────────────────────

def synthesize_scene(engine: TTSEngine, text: str, out_path: str,
                     target_wpm: float | None = None) -> VoiceClip:
    """
    Synthesize one scene. With `target_wpm`, measure the default-speed rate
    and re-synthesize at the speed that hits the target.
    """
    clip = engine.synthesize(text, out_path, speed=1.0)
    if not clip.words:
        clip.words = estimate_word_timings(text, clip.duration)
    clip.measured_wpm = words_per_minute(text, clip.duration)
    if not target_wpm or not clip.measured_wpm:
        return clip

    speed = max(SPEED_MIN, min(SPEED_MAX, target_wpm / clip.measured_wpm))
    if abs(speed - 1.0) <= RECALIBRATE_ABOVE:
        return clip
    clip = engine.synthesize(text, out_path, speed=round(speed, 3))
    if not clip.words:
        clip.words = estimate_word_timings(text, clip.duration)
    clip.measured_wpm = words_per_minute(text, clip.duration)
    return clip
