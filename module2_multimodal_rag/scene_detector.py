"""
scene_detector.py
=================
Extracts shot-level visual features from a video using PySceneDetect.

Features extracted:
  - shot_count:        Total number of shots/cuts in the video
  - avg_shot_duration: Mean duration of each shot in seconds
  - cut_frequency:     Cuts per second (shot_count / total_duration)
  - min_shot_duration: Shortest shot (indicates fast-cut style)
  - max_shot_duration: Longest shot (indicates slow/deliberate style)

Why these features matter for creator style:
  A creator who cuts every 1.5s is visually very different from one
  who holds a shot for 8s. Cut frequency directly correlates with
  perceived energy and pacing — a key dimension of visual style
  that transcripts cannot capture.
"""

from __future__ import annotations
from pathlib import Path


def extract_shot_features(video_path: str) -> dict:
    """
    Detect scene cuts and extract shot-level statistics.

    Uses PySceneDetect ContentDetector (threshold=27.0) which detects
    cuts based on HSV color histogram changes between frames.

    Args:
        video_path: Path to video file.

    Returns:
        Dict with keys:
          shot_count, avg_shot_duration, cut_frequency,
          min_shot_duration, max_shot_duration, total_duration
    """
    from scenedetect import open_video, SceneManager
    from scenedetect.detectors import ContentDetector

    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    # Defaults in case detection fails
    fallback = {
        "shot_count": 1,
        "avg_shot_duration": 30.0,
        "cut_frequency": 0.033,
        "min_shot_duration": 30.0,
        "max_shot_duration": 30.0,
        "total_duration": 30.0,
    }

    try:
        video = open_video(str(video_path))
        scene_manager = SceneManager()

        # ContentDetector: threshold 27 = standard sensitivity
        # Lower = more sensitive (detects subtle cuts)
        # Higher = less sensitive (only hard cuts)
        scene_manager.add_detector(ContentDetector(threshold=27.0))
        scene_manager.detect_scenes(video, show_progress=False)

        scene_list = scene_manager.get_scene_list()
        total_duration = video.duration.get_seconds() if video.duration else 30.0

        if not scene_list:
            # No cuts detected — likely a single continuous shot
            fallback["total_duration"] = total_duration
            fallback["avg_shot_duration"] = total_duration
            fallback["min_shot_duration"] = total_duration
            fallback["max_shot_duration"] = total_duration
            return fallback

        # Compute shot durations
        durations = [
            (end.get_seconds() - start.get_seconds())
            for start, end in scene_list
        ]

        shot_count       = len(durations)
        avg_shot_dur     = sum(durations) / shot_count
        cut_frequency    = shot_count / total_duration if total_duration > 0 else 0.0
        min_shot_dur     = min(durations)
        max_shot_dur     = max(durations)

        return {
            "shot_count":         shot_count,
            "avg_shot_duration":  round(avg_shot_dur, 3),
            "cut_frequency":      round(cut_frequency, 4),
            "min_shot_duration":  round(min_shot_dur, 3),
            "max_shot_duration":  round(max_shot_dur, 3),
            "total_duration":     round(total_duration, 3),
        }

    except Exception as e:
        print(f"[SceneDetector] Detection failed for {video_path.name}: {e}")
        print("[SceneDetector] Returning fallback shot features.")
        return fallback


def interpret_pacing(avg_shot_duration: float) -> str:
    """
    Convert avg_shot_duration to a human-readable pacing label.
    Used in the creator profile payload for LLM context injection.
    """
    if avg_shot_duration < 2.0:
        return "very fast-paced"
    elif avg_shot_duration < 4.0:
        return "fast-paced"
    elif avg_shot_duration < 7.0:
        return "moderate"
    elif avg_shot_duration < 12.0:
        return "slow"
    else:
        return "very slow / deliberate"
