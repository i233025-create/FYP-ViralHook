"""
evaluator.py — Measured evaluation of a rendered video
=======================================================
No LLM judging. The finished MP4 is measured with the *same instruments*
Module 2 used on the creator's real videos, then compared with the profile:

  pacing_match      PySceneDetect avg shot duration   vs visual_analysis.mean_avg_shot_duration
  speech_rate_match librosa duration + transcript wpm  vs audio_analysis.mean_speech_rate_wpm
  visual_match      CLIP(mean of rendered frames) · creator centroid, divided by the
                    creator's own leave-one-out similarity (how alike their videos are
                    to each other) and capped at 1.0
  style_fidelity    mean of the available matches above (None if none measurable)

  clip_alignment    CLIP cosine of each shot's middle frame vs its scene's clip_idea
                    (raw cosine, reported separately — topic, not style; placeholder
                    shots excluded, None if every shot is a placeholder)

Similarity is ratio-based: 1.0 when equal, falling to 0.0 when the measured
value is TOLERANCE× off in either direction (|ln(measured/target)| / ln 3).

Running this on the personalised and the generic render of the same script is
the video-level ablation for the FYP's "personalised vs generic" claim.
"""

from __future__ import annotations

import math
import shutil
import subprocess
from collections import Counter
from pathlib import Path
from typing import Callable

from .timeline import Timeline

TOLERANCE = 3.0


def ratio_similarity(measured: float | None, target: float | None,
                     tolerance: float = TOLERANCE) -> float | None:
    if not measured or not target or measured <= 0 or target <= 0:
        return None
    return round(max(0.0, 1.0 - abs(math.log(measured / target)) / math.log(tolerance)), 4)


def profile_targets(profile: dict) -> dict:
    return {
        "avg_shot_duration": (profile.get("visual_analysis") or {}).get("mean_avg_shot_duration"),
        "speech_rate_wpm": (profile.get("audio_analysis") or {}).get("mean_speech_rate_wpm"),
    }


def measure_video(video_path: str, transcript: str) -> dict:
    """Module 2's own feature extractors, run on the generated video."""
    from module2_multimodal_rag.audio_analyzer import extract_audio_features
    from module2_multimodal_rag.scene_detector import extract_shot_features

    shots = extract_shot_features(video_path)
    audio = extract_audio_features(video_path, transcript=transcript,
                                   video_duration=shots.get("total_duration", 0.0))
    return {
        "avg_shot_duration": shots["avg_shot_duration"],
        "shot_count": shots["shot_count"],
        "cut_frequency": shots["cut_frequency"],
        "speech_rate_wpm": audio["speech_rate_wpm"],
        "duration": audio["duration_seconds"],
    }


def extract_midframes(video_path: str, timeline: Timeline, out_dir: str | Path) -> list[tuple[str, str]]:
    """
    One JPEG from the middle of every real-asset shot → [(frame_path, scene clip_idea)].
    Placeholder cards are skipped: they print the query as text, which CLIP
    would read and score as a match.
    """
    if not shutil.which("ffmpeg"):
        return []
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for scene in timeline.scenes:
        for shot in scene.shots:
            if shot.asset is None or shot.asset.source == "placeholder":
                continue
            path = out_dir / f"frame_{len(frames):03d}.jpg"
            mid = (shot.start + shot.end) / 2
            result = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{mid:.3f}",
                                     "-i", str(video_path), "-frames:v", "1", "-q:v", "3", str(path)],
                                    capture_output=True)
            if result.returncode == 0 and path.exists():
                frames.append((str(path), scene.clip_idea or shot.query))
    return frames


def frame_scores(frames: list[tuple[str, str]], scorer, creator=None) -> tuple[dict | None, dict | None]:
    """(clip_alignment, visual) from one CLIP pass over the shot frames."""
    if not frames or scorer is None:
        return None, None
    try:
        emb = scorer.image_embeddings([path for path, _ in frames])
        texts = sorted({text for _, text in frames})
        text_emb = dict(zip(texts, scorer.text_embeddings(texts)))
    except Exception as e:
        print(f"[VideoEvaluator] CLIP unavailable: {e}")
        return None, None

    per_shot = [round(float(e @ text_emb[text]), 4) for e, (_, text) in zip(emb, frames)]
    alignment = {"mean": round(sum(per_shot) / len(per_shot), 4), "per_shot": per_shot}
    if creator is None:
        return alignment, None

    similarity = round(float(creator.similarity(emb.mean(axis=0))[0]), 4)
    reference = creator.self_similarity()
    visual = {"creator_similarity": similarity, "creator_self_similarity": reference,
              "talking_head_pct_creator": creator.talking_head_pct}
    return alignment, visual


def evaluate(video_path: str | Path, timeline: Timeline, profile: dict, work_dir: str | Path,
             clean_video: str | Path | None = None,
             measure: Callable[[str, str], dict] = measure_video,
             scorer=None, creator=None) -> dict:
    """
    Measure `video_path` against the creator profile (and, with `creator`, the
    creator's Module 2 visual vectors). `clean_video` (the render before
    captions) is used for CLIP frames so burned-in text doesn't bias scores.
    """
    transcript = " ".join(sc.voiceover for sc in timeline.scenes)
    measured = measure(str(video_path), transcript)
    targets = profile_targets(profile or {})

    if scorer is None:
        from .assets import ClipScorer
        scorer = ClipScorer()
    frames = extract_midframes(str(clean_video or video_path), timeline, Path(work_dir) / "eval_frames")
    alignment, visual = frame_scores(frames, scorer, creator)

    scores = {
        "pacing_match": ratio_similarity(measured.get("avg_shot_duration"), targets["avg_shot_duration"]),
        "speech_rate_match": ratio_similarity(measured.get("speech_rate_wpm"), targets["speech_rate_wpm"]),
        "visual_match": None,
    }
    if visual and visual["creator_self_similarity"]:
        ratio = visual["creator_similarity"] / visual["creator_self_similarity"]
        scores["visual_match"] = round(min(1.0, max(0.0, ratio)), 4)
    available = [v for v in scores.values() if v is not None]
    scores["style_fidelity"] = round(sum(available) / len(available), 4) if available else None

    sources = Counter(shot.asset.source for sc in timeline.scenes for shot in sc.shots if shot.asset)
    return {
        "mode": timeline.style.mode,
        "measured": measured,
        "target": targets,
        "scores": scores,
        "visual": visual,
        "clip_alignment": alignment,
        "asset_sources": dict(sources),
    }


def compare(personalised: dict, generic: dict) -> dict:
    """Side-by-side deltas (personalised − generic) for every shared score."""
    rows = {}
    for key in ("pacing_match", "speech_rate_match", "visual_match", "style_fidelity"):
        p, g = personalised["scores"].get(key), generic["scores"].get(key)
        rows[key] = {"personalised": p, "generic": g,
                     "delta": round(p - g, 4) if p is not None and g is not None else None}
    pa, ga = personalised.get("clip_alignment"), generic.get("clip_alignment")
    if pa and ga:
        rows["clip_alignment"] = {"personalised": pa["mean"], "generic": ga["mean"],
                                  "delta": round(pa["mean"] - ga["mean"], 4)}
    return rows
