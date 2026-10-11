"""
frame_extractor.py
==================
Extracts frames from a video file using FFmpeg.

Strategy:
  - 1 frame per second (fps=1) — enough to capture visual style
    without generating thousands of images for short-form videos
  - Frames saved as JPG to a temp directory
  - Caller is responsible for cleanup

Why 1fps:
  Short-form videos are 15-60s, so 1fps gives 15-60 frames — enough
  for CLIP to build a representative visual embedding without being
  slow or memory-heavy.
"""

import subprocess
import shutil
import tempfile
from pathlib import Path


def extract_frames(
    video_path: str,
    fps: float = 1.0,
    max_frames: int = 60,
) -> tuple[list[str], str]:
    """
    Extract frames from a video at the given fps rate.

    Args:
        video_path:  Path to input video file.
        fps:         Frames per second to extract. Default 1.0.
        max_frames:  Hard cap on number of frames (safety limit).

    Returns:
        Tuple of:
          - List of absolute paths to extracted JPG frames (sorted)
          - Temp directory path (caller must delete when done)

    Raises:
        FileNotFoundError: If video file doesn't exist.
        RuntimeError:      If FFmpeg extraction fails.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    # Create temp dir for frames
    temp_dir = tempfile.mkdtemp(prefix="viralhook_frames_")
    output_pattern = str(Path(temp_dir) / "frame_%04d.jpg")

    cmd = [
        "ffmpeg",
        "-i", str(video_path),
        "-vf", f"fps={fps}",        # extract at specified fps
        "-q:v", "2",                # JPEG quality (2=high, lower=better)
        "-frames:v", str(max_frames),  # hard cap
        output_pattern,
        "-y",                       # overwrite if exists
        "-loglevel", "error",       # suppress verbose output
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError(
            f"FFmpeg frame extraction failed for {video_path.name}:\n{result.stderr}"
        )

    # Collect extracted frames sorted by filename
    frame_paths = sorted(
        str(p) for p in Path(temp_dir).glob("frame_*.jpg")
    )

    if not frame_paths:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError(
            f"FFmpeg ran but extracted 0 frames from {video_path.name}. "
            "Check that the file is a valid video."
        )

    return frame_paths, temp_dir


def cleanup_frames(temp_dir: str) -> None:
    """Delete the temp directory created by extract_frames."""
    shutil.rmtree(temp_dir, ignore_errors=True)


def get_video_duration(video_path: str) -> float:
    """
    Return video duration in seconds using ffprobe.
    Returns 0.0 if ffprobe fails (non-critical).
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return float(result.stdout.strip())
    except Exception:
        return 0.0
