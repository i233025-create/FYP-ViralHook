"""
renderer.py — timeline.json → MP4 (FFmpeg)
===========================================
  1. every shot → normalised 1080×1920@30 segment
       video asset : scale-to-fill + crop, looped if the clip is too short
       image asset : 2× supersampled zoompan (Ken Burns), motion from the shot
  2. concat segments (stream copy)                         → video.mp4
  3. place each scene's voiceover at its start (adelay)    → voice.wav
       optional background music, ducked under the voice (sidechaincompress)
  4. burn ASS captions + mux audio                         → final MP4

Frame counts come from absolute times (round(end·fps) − round(start·fps)) so
rounding never drifts the picture away from the voiceover.

Captions:
  karaoke : 1–3 word chunks, current word highlighted (creator uses text overlays)
            With a measured caption_look (Module 2 OCR) the position, size, colours,
            box, case, chunk length and accent follow the creator's own captions:
            accent_mode 'word' highlights the spoken word, 'line' shows plain
            phrases and puts every other sentence in the accent colour.
  scene   : the scene's caption line for the whole scene (generic template)

Config (.env, optional):
  VIDEO_MUSIC         = path/to/track.mp3   (none by default)
  VIDEO_CAPTION_FONT  = DejaVu Sans
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable

from .timeline import Shot, Timeline

KARAOKE_WORDS = 3
HIGHLIGHT = "&H0000E5FF&"   # ASS colours are &HAABBGGRR → yellow
MUSIC_GAIN_DB = -16
SEGMENT_ENCODE = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p"]


class RenderError(RuntimeError):
    pass


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _run(cmd: list[str], cwd: str | Path | None = None):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RenderError(f"ffmpeg failed: {' '.join(cmd[:6])}…\n{result.stderr[-1500:]}")


# ─── Captions (ASS) ───────────────────────────────────────────────────────────

def ass_time(seconds: float) -> str:
    cs = max(0, int(round(seconds * 100)))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def ass_escape(text: str) -> str:
    """Strip characters ASS would read as override tags."""
    return re.sub(r"\s+", " ", text.replace("\\", "/").replace("{", "(").replace("}", ")")).strip()


def chunk_words(words: list, size: int = KARAOKE_WORDS) -> list[list]:
    """Groups of ≤ size words, also breaking after sentence punctuation."""
    chunks, current = [], []
    for w in words:
        current.append(w)
        if len(current) == size or re.search(r"[.!?,;:]$", w.word):
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)
    return chunks


def _norm(token: str) -> str:
    return re.sub(r"[^\w']", "", token).lower()


def punctuate(words: list, script: str) -> list:
    """Restore the script's punctuation on aligned words (TTS/ASR timings drop it),
    so chunking and sentence alternation see real sentence ends."""
    tokens = [t for t in script.split() if _norm(t)]
    out, ti = [], 0
    for w in words:
        for j in range(ti, min(ti + 4, len(tokens))):   # small lookahead absorbs ASR splits/merges
            if _norm(tokens[j]) == _norm(w.word):
                tail = re.search(r"[.!?,;:]+$", tokens[j])
                if tail and not re.search(r"[.!?,;:]$", w.word):
                    w = w.model_copy(update={"word": w.word + tail.group()})
                ti = j + 1
                break
        out.append(w)
    return out


def caption_font(look: dict | None) -> str:
    """VIDEO_CAPTION_FONT, else Inter for measured (modern creator) captions if installed."""
    if os.getenv("VIDEO_CAPTION_FONT"):
        return os.getenv("VIDEO_CAPTION_FONT")
    if look and shutil.which("fc-list"):
        found = subprocess.run(["fc-list", "Inter:style=SemiBold", "family"],
                               capture_output=True, text=True).stdout
        if found.strip():
            return "Inter SemiBold" if "Inter SemiBold" in found else "Inter"
    return "DejaVu Sans"


def karaoke_style(font: str, look: dict | None) -> str:
    """ASS style line: template look, or the creator's measured caption look."""
    if not look:
        return f"Style: Karaoke,{font},92,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,2,2,80,80,560,1"
    if look["boxed"]:   # opaque box behind the text, like the creator's
        border, outline, shadow, outline_col, back = 3, round(look["font_size"] * 0.18), 0, look["box"], look["box"]
    else:               # text straight on footage: thin dark edge + soft shadow keeps it legible
        border, outline, shadow, outline_col, back = 1, max(2, round(look["font_size"] * 0.05)), 2, \
            "&H50000000", "&H64000000"
    return (f"Style: Karaoke,{font},{look['font_size']},{look['primary']},&H000000FF,{outline_col},{back},"
            f"-1,0,0,0,100,100,0,0,{border},{outline},{shadow},2,80,80,{look['margin_v']},1")


def build_ass(timeline: Timeline) -> str:
    look = timeline.style.caption_look
    font = caption_font(look)
    w, h = timeline.width, timeline.height
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, \
Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, \
MarginV, Encoding
{karaoke_style(font, look)}
Style: Scene,{font},70,&H00FFFFFF,&H000000FF,&H00000000,&H8C000000,-1,0,0,0,100,100,0,0,3,16,0,8,90,90,260,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    sentence = 0          # running sentence count, for 'line' accent alternation
    for scene in timeline.scenes:
        if timeline.style.caption_style == "scene":
            if scene.caption:
                lines.append(f"Dialogue: 0,{ass_time(scene.start)},{ass_time(scene.end)},Scene,,0,0,0,,"
                             f"{ass_escape(scene.caption)}")
            continue

        chunks = chunk_words(punctuate(scene.voice.words, scene.voiceover),
                             look["words_per_chunk"] if look else KARAOKE_WORDS)
        mode = look.get("accent_mode") if look else "word"
        highlight = (look["accent"] + "&" if look else HIGHLIGHT) if mode else None
        primary = look["primary"] + "&" if look else "&H00FFFFFF&"
        upper = look["uppercase"] if look else True
        for ci, chunk in enumerate(chunks):
            next_start = chunks[ci + 1][0].start if ci + 1 < len(chunks) else scene.end - scene.start
            texts = [ass_escape(w.word).upper() if upper else ass_escape(w.word) for w in chunk]
            if mode != "word":   # creator shows plain phrases, no per-word highlight
                end = scene.start + min(next_start, chunk[-1].end + 0.35)
                colour = f"{{\\c{highlight}}}" if mode == "line" and sentence % 2 else ""
                lines.append(f"Dialogue: 0,{ass_time(scene.start + chunk[0].start)},{ass_time(end)},"
                             f"Karaoke,,0,0,0,,{colour}{' '.join(texts)}")
                if re.search(r"[.!?]$", chunk[-1].word):
                    sentence += 1
                continue
            for wi, word in enumerate(chunk):
                start = scene.start + word.start
                end = scene.start + (chunk[wi + 1].start if wi + 1 < len(chunk)
                                     else min(next_start, word.end + 0.35))
                if end <= start:
                    continue
                shown = " ".join(f"{{\\c{highlight}}}{t}{{\\c{primary}}}" if i == wi else t
                                 for i, t in enumerate(texts))
                lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Karaoke,,0,0,0,,{shown}")
    return header + "\n".join(lines) + "\n"


# ─── Shots ────────────────────────────────────────────────────────────────────

def frame_count(start: float, end: float, fps: int) -> int:
    return max(1, round(end * fps) - round(start * fps))


def zoompan_expr(motion: str, strength: float, frames: int) -> tuple[str, str, str]:
    """(z, x, y) zoompan expressions for a Ken Burns move over `frames`."""
    p = f"on/{frames}"
    centre_x, centre_y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    if motion == "zoom_in":
        return f"1+{strength}*{p}", centre_x, centre_y
    if motion == "zoom_out":
        return f"1+{strength}*(1-{p})", centre_x, centre_y
    if motion == "pan_right":
        return f"1+{strength}", f"(iw-iw/zoom)*{p}", centre_y
    if motion == "pan_left":
        return f"1+{strength}", f"(iw-iw/zoom)*(1-{p})", centre_y
    return "1", centre_x, centre_y


def shot_command(shot: Shot, out_path: str, timeline: Timeline) -> list[str]:
    if shot.asset is None:
        raise RenderError(f"Shot {shot.query!r} has no asset")
    w, h, fps = timeline.width, timeline.height, timeline.fps
    frames = frame_count(shot.start, shot.end, fps)
    fill = "scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"

    if shot.asset.kind == "video":
        vf = fill.format(W=w, H=h) + f",fps={fps},setsar=1,format=yuv420p"
        inputs = ["-stream_loop", "-1", "-i", shot.asset.path]
    else:
        z, x, y = zoompan_expr(shot.motion, timeline.style.zoom_strength, frames)
        vf = (fill.format(W=2 * w, H=2 * h)
              + f",zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={w}x{h}:fps={fps},setsar=1,format=yuv420p")
        inputs = ["-i", shot.asset.path]

    return (["ffmpeg", "-y", "-loglevel", "error", *inputs, "-vf", vf, "-frames:v", str(frames),
             "-r", str(fps), "-an", *SEGMENT_ENCODE, out_path])


# ─── Audio ────────────────────────────────────────────────────────────────────

def audio_command(timeline: Timeline, out_path: str, music: str | None = None) -> list[str]:
    total = round(timeline.duration, 3)
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    parts = []
    for i, scene in enumerate(timeline.scenes):
        cmd += ["-i", scene.voice.path]
        ms = int(round(scene.start * 1000))
        parts.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[a{i}]")
    n = len(timeline.scenes)
    labels = "".join(f"[a{i}]" for i in range(n))
    parts.append(f"{labels}amix=inputs={n}:normalize=0:dropout_transition=0,apad,atrim=0:{total}[voice]")

    if music:
        cmd += ["-stream_loop", "-1", "-i", music]
        parts += [
            "[voice]asplit=2[vk][vm]",
            f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo,volume={MUSIC_GAIN_DB}dB[m]",
            "[m][vk]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[duck]",
            f"[duck][vm]amix=inputs=2:normalize=0,atrim=0:{total}[out]",
        ]
        out = "[out]"
    else:
        out = "[voice]"
    return cmd + ["-filter_complex", ";".join(parts), "-map", out, "-ar", "48000", out_path]


# ─── Render ───────────────────────────────────────────────────────────────────

def render(timeline: Timeline, out_path: str | Path, work_dir: str | Path,
           on_progress: Callable[[int, int], None] | None = None) -> Path:
    """Render `timeline` to `out_path`. Intermediate files go to `work_dir`."""
    if not ffmpeg_available():
        raise RenderError("ffmpeg not found on PATH")
    work = Path(work_dir).resolve()
    (work / "segments").mkdir(parents=True, exist_ok=True)
    out_path = Path(out_path).resolve()

    shots = [shot for scene in timeline.scenes for shot in scene.shots]
    names = []
    for i, shot in enumerate(shots):
        name = f"segments/shot_{i:03d}.mp4"
        _run(shot_command(shot, str(work / name), timeline))
        names.append(name)
        if on_progress:
            on_progress(i + 1, len(shots))

    (work / "segments.txt").write_text("".join(f"file '{n}'\n" for n in names), encoding="utf-8")
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
          "-i", "segments.txt", "-c", "copy", "video.mp4"], cwd=work)

    music = os.getenv("VIDEO_MUSIC") or None
    if music and not Path(music).exists():
        print(f"[Renderer] VIDEO_MUSIC not found: {music}; rendering without music")
        music = None
    _run(audio_command(timeline, str(work / "voice.wav"), music))

    (work / "captions.ass").write_text(build_ass(timeline), encoding="utf-8")
    # Relative ASS path + cwd avoids the ass filter's path-escaping rules
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", "video.mp4", "-i", "voice.wav",
          "-vf", "ass=captions.ass", "-map", "0:v", "-map", "1:a",
          "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(out_path)], cwd=work)
    return out_path
