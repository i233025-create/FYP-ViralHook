"""
transcriber.py — Audio Download & Whisper Transcription
=========================================================
This module handles two distinct responsibilities:
  1. Downloading audio-only streams from YouTube Shorts using yt-dlp.
  2. Transcribing the downloaded audio using OpenAI Whisper (local, CPU mode).

Why keep these together?
  Both steps are tightly coupled — the output of download is the input of
  transcribe — so grouping them reduces boilerplate in the main pipeline
  and makes unit testing straightforward.

SYSTEM REQUIREMENT:
  ffmpeg must be installed and on your system PATH.
  yt-dlp uses ffmpeg under the hood to convert audio streams.
  If ffmpeg is missing, yt-dlp will fail — we catch and surface that error.
"""

import os
import time
import whisper              # openai-whisper: local speech-to-text model
import yt_dlp               # YouTube downloader library
from rich.console import Console

# ─── Module-level Whisper Model Cache ─────────────────────────────────────────
# We use a module-level variable to cache the loaded Whisper model.
# Loading Whisper reads ~75 MB from disk and initialises PyTorch layers —
# doing this ONCE and reusing it is critical for performance when processing
# multiple videos in a loop.
_whisper_model = None

console = Console()


def download_audio(url: str, output_dir: str) -> str:
    """
    Download the audio track of a YouTube video using yt-dlp.

    We download audio-only (no video) because Whisper only needs the audio
    signal — downloading the full video would waste bandwidth and disk space.

    yt-dlp is chosen over pytube because it is actively maintained, handles
    YouTube's frequent API changes, and has robust error handling.

    Args:
        url:        Full YouTube (or Shorts) URL to download.
        output_dir: Directory path where the audio file will be saved.

    Returns:
        Absolute path to the downloaded audio file (WAV format).

    Raises:
        RuntimeError: If ffmpeg is not found or the download fails.
        ValueError:   If the URL is invalid or the video is unavailable.
    """
    os.makedirs(output_dir, exist_ok=True)

    # yt-dlp configuration dictionary — core download settings.
    ydl_opts = {
        # "bestaudio/best" tells yt-dlp to prefer the highest-quality audio
        # stream; falls back to the best overall stream as a backup.
        "format": "bestaudio/best",

        # %(id)s gives us the YouTube video ID (e.g. "yILbNB9QPOA") as the
        # filename — guaranteed unique, no special characters.
        "outtmpl": os.path.join(output_dir, "%(id)s.%(ext)s"),

        # Post-processor: convert the downloaded stream to WAV.
        # WAV is uncompressed — Whisper handles it natively and accurately
        # without lossy re-encoding artefacts.
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
            "preferredquality": "192",
        }],

        # Suppress yt-dlp's own verbose output — we handle progress display
        # ourselves using Rich for a consistent terminal experience.
        "quiet": True,
        "no_warnings": True,
    }

    console.print(f"  [cyan]↓ Downloading audio:[/cyan] {url}")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # extract_info() downloads the video AND returns metadata dict.
            # We need the metadata to reconstruct the output filename.
            info = ydl.extract_info(url, download=True)
            video_id = info.get("id", "unknown")

        # After post-processing, the file extension is always .wav
        audio_path = os.path.join(output_dir, f"{video_id}.wav")

        if not os.path.exists(audio_path):
            # This usually means ffmpeg is missing — yt-dlp downloads the
            # raw stream but the post-processor silently fails without ffmpeg.
            raise RuntimeError(
                f"Audio file not found at '{audio_path}'. "
                "This usually means ffmpeg is not installed or not on PATH. "
                "Windows: download from https://ffmpeg.org/download.html and add to PATH."
            )

        console.print(f"  [green]✓ Audio saved:[/green] {os.path.basename(audio_path)}")
        return audio_path

    except yt_dlp.utils.DownloadError as e:
        raise ValueError(f"Failed to download video from '{url}': {e}") from e

    except Exception as e:
        raise RuntimeError(f"Unexpected error during audio download: {e}") from e


def transcribe_audio(audio_path: str, model_size: str = "tiny", language: str = None, task: str = "translate") -> str:
    """
    Transcribe (or translate) an audio file using OpenAI Whisper.

    task="translate" tells Whisper to output English regardless of the
    input language — ideal for Urdu/Hindi creators so the LLM receives
    clean English text instead of mixed-script output.

    task="transcribe" outputs in the original spoken language.

    Args:
        audio_path:  Path to the audio/video file.
        model_size:  Whisper model variant ("tiny", "base", etc.)
        language:    ISO 639-1 language code or None for auto-detect.
        task:        "translate" (to English) or "transcribe" (original language).

    Returns:
        Cleaned transcript string in English (if task="translate").

    Raises:
        FileNotFoundError: If audio_path doesn't exist.
        RuntimeError:      If Whisper fails.
    """
    global _whisper_model  # Access the module-level model cache

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: '{audio_path}'")

    # ─── Lazy Model Loading ───────────────────────────────────────────────────
    # Only load the Whisper model on the first call in a session.
    # This "lazy loading" pattern avoids reloading ~75 MB of model weights
    # on every call — a significant performance win across multiple videos.
    if _whisper_model is None:
        console.print(
            f"\n  [yellow]⚙ Loading Whisper '{model_size}' model...[/yellow] "
            "(first run downloads ~75MB, then cached permanently)"
        )
        _whisper_model = whisper.load_model(model_size)
        console.print(f"  [green]✓ Whisper model loaded[/green]")

    console.print(f"  [cyan]🎙 Transcribing:[/cyan] {os.path.basename(audio_path)}")
    start_time = time.time()

    try:
        # whisper.transcribe() is the main inference call.
        # task="translate" outputs English regardless of input language.
        # task="transcribe" outputs in the original spoken language.
        # fp16=False required on CPU.
        result = _whisper_model.transcribe(
            audio_path, fp16=False, language=language, task=task
        )
        transcript: str = result.get("text", "").strip()

        # ── Clean up hallucinated garbage characters ──────────────────────
        # Whisper tiny sometimes hallucinates non-Latin/non-Urdu characters
        # (Japanese, Chinese, Cyrillic) when audio is noisy or music-heavy.
        # We keep only printable ASCII + Urdu Unicode block (0600-06FF).
        import re
        transcript = re.sub(
            r"[^\x00-\x7F\u0600-\u06FF\u0750-\u077F\s]", "", transcript
        ).strip()

        elapsed = time.time() - start_time
        console.print(
            f"  [green]✓ Transcription complete[/green] "
            f"({elapsed:.1f}s, {len(transcript)} characters)"
        )

        if not transcript:
            console.print(
                "  [yellow]⚠ Warning:[/yellow] Empty transcript — "
                "audio may be silent or too short."
            )
            return ""

        return transcript

    except Exception as e:
        raise RuntimeError(
            f"Whisper transcription failed for '{audio_path}': {e}"
        ) from e


def get_local_videos(video_dir: str) -> list[str]:
    """
    Scan a directory for video files and return their paths.

    Supports common video formats: mp4, mov, mkv, avi, webm.
    Files are sorted alphabetically for consistent processing order.

    Args:
        video_dir: Path to the directory containing video files.

    Returns:
        Sorted list of absolute paths to video files found.

    Raises:
        ValueError: If the directory doesn't exist or contains no videos.
    """
    if not os.path.exists(video_dir):
        raise ValueError(
            f"Input video directory not found: '{video_dir}'. "
            "Create it and drop your video files inside."
        )

    supported_extensions = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
    video_files = sorted([
        os.path.join(video_dir, f)
        for f in os.listdir(video_dir)
        if os.path.splitext(f)[1].lower() in supported_extensions
    ])

    if not video_files:
        raise ValueError(
            f"No video files found in '{video_dir}'. "
            f"Supported formats: {', '.join(supported_extensions)}. "
            "Drop your video files into that folder and run again."
        )

    console.print(f"  [green]✓ Found {len(video_files)} video file(s) in '{video_dir}'[/green]")
    for i, f in enumerate(video_files, 1):
        console.print(f"    {i}. {os.path.basename(f)}")

    return video_files


def process_local_video(
    video_path: str,
    video_index: int,
    total: int,
    model_size: str,
    language: str = None,
    task: str = "translate",
) -> str:
    """
    Transcribe a local video file directly using Whisper.

    Unlike process_video() which downloads from YouTube, this function
    passes the local file directly to Whisper — no ffmpeg download step
    needed (though ffmpeg is still used internally by Whisper for decoding).

    Args:
        video_path:  Full path to the local video file.
        video_index: 1-based index for progress display.
        total:       Total number of videos being processed.
        model_size:  Whisper model size (e.g. "tiny").

    Returns:
        Transcript text as a plain string.

    Raises:
        FileNotFoundError: If the video file doesn't exist.
        RuntimeError:      If transcription fails.
    """
    console.print(
        f"\n[bold blue]━━ Video {video_index}/{total} "
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold blue]"
    )
    console.print(f"  [dim]File:[/dim] {os.path.basename(video_path)}")

    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: '{video_path}'")

    # Whisper can transcribe video files directly — it extracts the audio
    # track internally using ffmpeg. No manual audio extraction needed.
    return transcribe_audio(video_path, model_size, language, task)


def process_video(
    url: str,
    video_index: int,
    total: int,
    output_dir: str,
    model_size: str,
    language: str = None,
    task: str = "translate",
) -> str:
    """
    End-to-end handler for a single video: download → transcribe → cleanup.

    This is the primary entry point called by main.py.
    It coordinates download_audio() and transcribe_audio(), then deletes
    the temporary audio file to keep the workspace clean.

    Args:
        url:         YouTube Shorts URL to process.
        video_index: 1-based index of this video (used for progress display).
        total:       Total number of videos being processed (for display).
        output_dir:  Directory to temporarily store downloaded audio.
        model_size:  Whisper model size string (e.g., "tiny").

    Returns:
        The full transcript text for this video as a plain string.

    Raises:
        ValueError:   Propagated from download_audio() for bad URLs.
        RuntimeError: Propagated for download or transcription failures.
    """
    console.print(
        f"\n[bold blue]━━ Video {video_index}/{total} "
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold blue]"
    )
    console.print(f"  [dim]URL:[/dim] {url}")

    # Track the audio path so the finally block can clean it up
    # even if an exception occurs mid-process.
    audio_path: str = ""

    try:
        # ── Step 1: Download audio from YouTube ──────────────────────────────
        audio_path = download_audio(url, output_dir)

        # ── Step 2: Transcribe audio to text ─────────────────────────────────
        transcript = transcribe_audio(audio_path, model_size, language, task)

        return transcript

    finally:
        # ── Step 3: Cleanup temp audio file ──────────────────────────────────
        # The finally block runs regardless of success or exception.
        # This guarantees temp files are always deleted — critical for keeping
        # temp_audio/ from accumulating files over multiple pipeline runs.
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
            console.print(
                f"  [dim]🗑 Temp audio deleted:[/dim] {os.path.basename(audio_path)}"
            )
