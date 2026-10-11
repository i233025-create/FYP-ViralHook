"""
json_to_premiere_xml.py — Module 3: Storyboard to Premiere Pro XML
====================================================================
Part of the ViralHook multi-agent pipeline (FYP POC).

Converts the Scripting Agent's output (test_scripting_comparison_output.json)
into two production-ready files:

  1. <project_name>.xml  — FCP XML / xmeml sequence importable into
                           Adobe Premiere Pro and DaVinci Resolve.

  2. <project_name>.srt  — SubRip subtitle file with captions timed
                           to each scene, ready to import or burn-in.

Timeline Structure:
  ┌─────────────────────────────────────────────────────────────────┐
  │ V2  │ [Caption: "Motivation ≠ Hustle?"] [Caption: "Next..."] │
  │ V1  │ [Colour Block: clip_idea text] [Colour Block: ...]     │
  │     │ ←──────── Cross-dissolve transitions ────────────────→  │
  │ A1  │ [Empty gap — drop voiceover here] [Empty gap: ...]     │
  └─────────────────────────────────────────────────────────────────┘

  V1 (Video Track 1): Solid colour placeholder clips, one per scene.
     Each clip is labelled with the scene's clip_idea description so
     the editor knows exactly what footage to swap in.

  V2 (Video Track 2): Caption title clips using Premiere's legacy
     title generator format. Text is pre-timed to each scene.

  A1 (Audio Track 1): Empty audio gaps pre-timed to each scene.
     Creator drops their voiceover recordings into the reserved slots.
     Clip names show the voiceover text as a guide.

  Transitions: 1-frame cross-dissolve between consecutive V1 clips.
     This is the standard "cut" equivalent in FCP XML — it tells
     Premiere the edit points are intentional, not missing media.

Sequence Specs:
  Resolution : 1080 × 1920 (9:16 vertical — Instagram Reels / Shorts)
  Frame Rate : 30 FPS (configurable via FPS constant)
  Timebase   : 30 (FCP XML requirement — must match FPS)
  Depth      : 32-bit float colour
  Audio      : 48000 Hz, stereo

Usage:
  python json_to_premiere_xml.py
  python json_to_premiere_xml.py --input path/to/output.json --mode retrieval_only

Input:
  pipeline/test_scripting_comparison_output.json  (default)
  Uses 'full_pipeline' mode script by default (best quality).

Output:
  pipeline/output/<project_name>.xml
  pipeline/output/<project_name>.srt
"""

from __future__ import annotations

import argparse
import json
import os
import re
import textwrap
import uuid
from pathlib import Path
from xml.dom import minidom
from xml.etree import ElementTree as ET


# ─── Sequence Configuration ────────────────────────────────────────────────────
FPS = 30                      # Frames per second
TIMEBASE = 30                 # FCP XML timebase (must equal FPS for whole-frame edits)
WIDTH = 1080                  # Pixels — 9:16 vertical
HEIGHT = 1920
SAMPLE_RATE = 48000           # Audio sample rate (Hz)
AUDIO_CHANNELS = 2            # Stereo

# Placeholder clip colours per scene (cycles through these)
# Values are Premiere's internal colour codes (R, G, B as 0.0-1.0 floats)
PLACEHOLDER_COLOURS = [
    (0.12, 0.12, 0.20),   # Dark navy — professional, neutral
    (0.10, 0.18, 0.12),   # Dark forest green
    (0.20, 0.10, 0.10),   # Dark maroon
    (0.10, 0.15, 0.20),   # Dark teal
    (0.18, 0.12, 0.18),   # Dark purple
]

# Cross-dissolve transition duration in frames
TRANSITION_FRAMES = 1         # 1-frame dissolve = clean cut with intentional edit point

# Output directory
OUTPUT_DIR = Path(__file__).parent / "output"


# ─── Timecode Parsing ──────────────────────────────────────────────────────────

def parse_timecode(tc: str) -> tuple[int, int]:
    """
    Parse a timecode string like "0:03-0:08" into (start_frame, end_frame).

    Timecodes use M:SS format. Converts to total seconds then multiplies
    by FPS to get frame numbers.

    Args:
        tc: Timecode string in "M:SS-M:SS" format.

    Returns:
        Tuple of (start_frame, end_frame) as integers.

    Examples:
        "0:00-0:05" → (0, 150)    [at 30fps: 5s × 30 = 150 frames]
        "0:05-0:11" → (150, 330)
    """
    pattern = r"(\d+):(\d+)\s*[-–]\s*(\d+):(\d+)"
    match = re.match(pattern, tc.strip())
    if not match:
        raise ValueError(f"Cannot parse timecode: '{tc}'. Expected format: M:SS-M:SS")

    start_min, start_sec, end_min, end_sec = map(int, match.groups())
    start_total_sec = start_min * 60 + start_sec
    end_total_sec = end_min * 60 + end_sec

    start_frame = start_total_sec * FPS
    end_frame = end_total_sec * FPS

    if end_frame <= start_frame:
        raise ValueError(
            f"Timecode '{tc}': end ({end_frame}) must be after start ({start_frame})"
        )

    return start_frame, end_frame


def frames_to_srt_time(frames: int) -> str:
    """
    Convert a frame count to SRT timestamp format: HH:MM:SS,mmm

    Args:
        frames: Frame count at FPS.

    Returns:
        SRT timestamp string, e.g. "00:00:05,000"
    """
    total_ms = int((frames / FPS) * 1000)
    hours = total_ms // 3600000
    minutes = (total_ms % 3600000) // 60000
    seconds = (total_ms % 60000) // 1000
    ms = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"


# ─── XML Helpers ───────────────────────────────────────────────────────────────

def _uid() -> str:
    """Generate a unique ID for FCP XML elements (without hyphens)."""
    return uuid.uuid4().hex.upper()


def _el(parent: ET.Element, tag: str, text: str = None, **attrs) -> ET.Element:
    """Create a child XML element with optional text and attributes."""
    el = ET.SubElement(parent, tag)
    if text is not None:
        el.text = str(text)
    for k, v in attrs.items():
        el.set(k, str(v))
    return el


def _rate_element(parent: ET.Element, fps: int = FPS) -> None:
    """
    Add a <rate> element to parent.

    FCP XML requires rate elements on sequences, clips, and media.
    ntsc="FALSE" means we're using exact integer frame rates (30, not 29.97).
    """
    rate = ET.SubElement(parent, "rate")
    ET.SubElement(rate, "timebase").text = str(fps)
    ET.SubElement(rate, "ntsc").text = "FALSE"


def _colour_element(parent: ET.Element, r: float, g: float, b: float) -> None:
    """Add a <color> element with R, G, B components (0.0 to 1.0 range)."""
    color = ET.SubElement(parent, "color")
    ET.SubElement(color, "red").text = str(round(r, 4))
    ET.SubElement(color, "green").text = str(round(g, 4))
    ET.SubElement(color, "blue").text = str(round(b, 4))
    ET.SubElement(color, "alpha").text = "1.0"


# ─── Master Clip Registry ──────────────────────────────────────────────────────
# FCP XML requires each unique asset to be declared once as a <clip> in the
# <media> section (or inline) with a unique ID, then referenced by ID on
# the timeline. We maintain a registry to avoid duplicate declarations.

class ClipRegistry:
    """Tracks registered master clips for the XML <media> section."""

    def __init__(self):
        self._clips: dict[str, dict] = {}  # name → {id, duration_frames, type}

    def register(self, name: str, duration_frames: int, clip_type: str = "video") -> str:
        """
        Register a clip and return its unique ID.
        If already registered, returns existing ID (idempotent).
        """
        if name not in self._clips:
            self._clips[name] = {
                "id": f"clip_{_uid()[:8]}",
                "duration_frames": duration_frames,
                "type": clip_type,
            }
        return self._clips[name]["id"]

    def get(self, name: str) -> dict:
        return self._clips[name]

    def all(self) -> dict:
        return self._clips


# ─── Core XML Builder ──────────────────────────────────────────────────────────

def build_xml(project_name: str, scenes: list[dict]) -> ET.Element:
    """
    Build the complete FCP XML / xmeml Element tree for the sequence.

    FCP XML structure:
      <xmeml>
        <sequence>
          <rate>
          <media>
            <video>
              <track> (V1 — colour placeholders)
              <track> (V2 — caption titles)
            <audio>
              <track> (A1 — empty voiceover slots)

    Each scene becomes:
      V1: A solid-colour clip with clip_idea as the clip name
      V2: A text/title clip with the caption
      A1: An empty audio gap with voiceover text as clip name

    Args:
        project_name: Used as the sequence name.
        scenes:       List of scene dicts with timecode, clip_idea, caption, voiceover.

    Returns:
        Root <xmeml> ET.Element.
    """
    # Parse all timecodes first to validate and get total duration
    parsed_scenes = []
    for scene in scenes:
        start_f, end_f = parse_timecode(scene["timecode"])
        parsed_scenes.append({
            **scene,
            "start_frame": start_f,
            "end_frame": end_f,
            "duration_frames": end_f - start_f,
        })

    total_frames = max(s["end_frame"] for s in parsed_scenes)

    # ── Root element ──────────────────────────────────────────────────────────
    root = ET.Element("xmeml", version="4")
    seq = ET.SubElement(root, "sequence", id=f"seq_{_uid()[:8]}")
    ET.SubElement(seq, "name").text = project_name
    ET.SubElement(seq, "duration").text = str(total_frames)
    _rate_element(seq)

    # ── Sequence in/out points ────────────────────────────────────────────────
    ET.SubElement(seq, "in").text = "-1"
    ET.SubElement(seq, "out").text = "-1"

    # ── Sequence settings (resolution, pixel aspect, etc.) ───────────────────
    settings = ET.SubElement(seq, "samplecharacteristics")
    _rate_element(settings)
    ET.SubElement(settings, "width").text = str(WIDTH)
    ET.SubElement(settings, "height").text = str(HEIGHT)
    ET.SubElement(settings, "pixelaspectratio").text = "square"
    ET.SubElement(settings, "fielddominance").text = "none"
    ET.SubElement(settings, "colordepth").text = "32"

    # ── Media container ───────────────────────────────────────────────────────
    media = ET.SubElement(seq, "media")

    # ──────────────────────────────────────────────────────────────────────────
    # VIDEO TRACKS
    # ──────────────────────────────────────────────────────────────────────────
    video = ET.SubElement(media, "video")

    # Video format settings
    v_format = ET.SubElement(video, "format")
    v_chars = ET.SubElement(v_format, "samplecharacteristics")
    _rate_element(v_chars)
    ET.SubElement(v_chars, "width").text = str(WIDTH)
    ET.SubElement(v_chars, "height").text = str(HEIGHT)
    ET.SubElement(v_chars, "pixelaspectratio").text = "square"
    ET.SubElement(v_chars, "fielddominance").text = "none"

    # ── V1: Colour placeholder clips ─────────────────────────────────────────
    v1_track = ET.SubElement(video, "track")

    for i, scene in enumerate(parsed_scenes):
        colour = PLACEHOLDER_COLOURS[i % len(PLACEHOLDER_COLOURS)]
        clip_name = f"Scene{scene.get('scene_id', i+1)}_Placeholder"

        # Truncate clip_idea for use as clip label (Premiere shows this)
        idea_label = scene.get("clip_idea", "")[:80].replace('"', "'")

        # Each clip item on the V1 track
        clip_item = ET.SubElement(v1_track, "clipitem",
                                   id=f"v1_clip_{i+1}_{_uid()[:6]}")
        ET.SubElement(clip_item, "name").text = f"[V{i+1}] {idea_label}"
        ET.SubElement(clip_item, "duration").text = str(scene["duration_frames"])
        _rate_element(clip_item)
        ET.SubElement(clip_item, "start").text = str(scene["start_frame"])
        ET.SubElement(clip_item, "end").text = str(scene["end_frame"])
        ET.SubElement(clip_item, "in").text = "0"
        ET.SubElement(clip_item, "out").text = str(scene["duration_frames"])

        # Solid colour generator as the clip source
        # This creates a colour matte — no external file needed
        file_el = ET.SubElement(clip_item, "file", id=f"file_v1_{i+1}_{_uid()[:6]}")
        ET.SubElement(file_el, "name").text = clip_name
        ET.SubElement(file_el, "duration").text = str(scene["duration_frames"])
        _rate_element(file_el)
        # pathurl left empty — this tells Premiere it's a generator/offline clip
        ET.SubElement(file_el, "pathurl").text = ""

        media_el = ET.SubElement(file_el, "media")
        v_media = ET.SubElement(media_el, "video")
        ET.SubElement(v_media, "duration").text = str(scene["duration_frames"])
        v_chars2 = ET.SubElement(v_media, "samplecharacteristics")
        _rate_element(v_chars2)
        ET.SubElement(v_chars2, "width").text = str(WIDTH)
        ET.SubElement(v_chars2, "height").text = str(HEIGHT)

        # Colour matte effect — Premiere will render this as a solid colour
        effect = ET.SubElement(clip_item, "filter")
        effect_el = ET.SubElement(effect, "effect")
        ET.SubElement(effect_el, "name").text = "Color Matte"
        ET.SubElement(effect_el, "effectid").text = "colormatte"
        ET.SubElement(effect_el, "effecttype").text = "generator"
        ET.SubElement(effect_el, "mediatype").text = "video"
        param = ET.SubElement(effect_el, "parameter")
        ET.SubElement(param, "name").text = "color"
        ET.SubElement(param, "parameterid").text = "color"
        val = ET.SubElement(param, "value")
        _colour_element(val, *colour)

        # Cross-dissolve transition between clips (except after last clip)
        if i < len(parsed_scenes) - 1:
            transition = ET.SubElement(v1_track, "transitionitem")
            ET.SubElement(transition, "start").text = str(scene["end_frame"] - TRANSITION_FRAMES)
            ET.SubElement(transition, "end").text = str(scene["end_frame"] + TRANSITION_FRAMES)
            ET.SubElement(transition, "alignment").text = "center"
            ET.SubElement(transition, "cutPointFrame").text = str(scene["end_frame"])
            t_effect = ET.SubElement(transition, "effect")
            ET.SubElement(t_effect, "name").text = "Cross Dissolve"
            ET.SubElement(t_effect, "effectid").text = "dissolve"
            ET.SubElement(t_effect, "effecttype").text = "transition"
            ET.SubElement(t_effect, "mediatype").text = "video"

    # ── V2: Caption title clips ───────────────────────────────────────────────
    v2_track = ET.SubElement(video, "track")

    for i, scene in enumerate(parsed_scenes):
        caption = scene.get("caption", "")
        if not caption:
            continue

        caption_item = ET.SubElement(v2_track, "clipitem",
                                      id=f"v2_caption_{i+1}_{_uid()[:6]}")
        ET.SubElement(caption_item, "name").text = f"[CAP] {caption[:50]}"
        ET.SubElement(caption_item, "duration").text = str(scene["duration_frames"])
        _rate_element(caption_item)
        ET.SubElement(caption_item, "start").text = str(scene["start_frame"])
        ET.SubElement(caption_item, "end").text = str(scene["end_frame"])
        ET.SubElement(caption_item, "in").text = "0"
        ET.SubElement(caption_item, "out").text = str(scene["duration_frames"])

        # Premiere legacy title generator
        # This creates an editable text layer the editor can restyle
        title_file = ET.SubElement(caption_item, "file",
                                    id=f"file_v2_{i+1}_{_uid()[:6]}")
        ET.SubElement(title_file, "name").text = f"Caption_{i+1}"
        ET.SubElement(title_file, "duration").text = str(scene["duration_frames"])
        _rate_element(title_file)
        ET.SubElement(title_file, "pathurl").text = ""

        t_media = ET.SubElement(title_file, "media")
        t_video = ET.SubElement(t_media, "video")
        ET.SubElement(t_video, "duration").text = str(scene["duration_frames"])

        # Text effect — Premiere parses this to create an editable title
        cap_filter = ET.SubElement(caption_item, "filter")
        cap_effect = ET.SubElement(cap_filter, "effect")
        ET.SubElement(cap_effect, "name").text = "Premiere Title"
        ET.SubElement(cap_effect, "effectid").text = "PremierTitle"
        ET.SubElement(cap_effect, "effecttype").text = "generator"
        ET.SubElement(cap_effect, "mediatype").text = "video"

        # Title text parameter
        text_param = ET.SubElement(cap_effect, "parameter")
        ET.SubElement(text_param, "name").text = "Text"
        ET.SubElement(text_param, "parameterid").text = "Text"
        ET.SubElement(text_param, "value").text = caption

        # Font size parameter (large, readable on 1920px height)
        font_param = ET.SubElement(cap_effect, "parameter")
        ET.SubElement(font_param, "name").text = "Font Size"
        ET.SubElement(font_param, "parameterid").text = "FontSize"
        ET.SubElement(font_param, "value").text = "80"

        # Vertical position — lower third (70% down the frame)
        pos_param = ET.SubElement(cap_effect, "parameter")
        ET.SubElement(pos_param, "name").text = "Origin"
        ET.SubElement(pos_param, "parameterid").text = "origin"
        val_el = ET.SubElement(pos_param, "value")
        ET.SubElement(val_el, "horiz").text = "0"       # Centred horizontally
        ET.SubElement(val_el, "vert").text = "560"      # Lower third (1920 * 0.7 / 2 ≈ 672)

    # ──────────────────────────────────────────────────────────────────────────
    # AUDIO TRACKS
    # ──────────────────────────────────────────────────────────────────────────
    audio = ET.SubElement(media, "audio")

    # Audio format settings
    a_format = ET.SubElement(audio, "format")
    a_chars = ET.SubElement(a_format, "samplecharacteristics")
    ET.SubElement(a_chars, "depth").text = "16"
    ET.SubElement(a_chars, "samplerate").text = str(SAMPLE_RATE)

    # ── A1: Empty voiceover slots ─────────────────────────────────────────────
    # Each slot is a silent/empty audio clip. The editor sees the reserved
    # duration and the voiceover text as the clip name — they drop their
    # recorded audio directly onto these slots.
    a1_track = ET.SubElement(audio, "track")

    for i, scene in enumerate(parsed_scenes):
        voiceover = scene.get("voiceover", "")
        vo_label = voiceover[:60].replace('"', "'") if voiceover else f"Voiceover {i+1}"

        audio_item = ET.SubElement(a1_track, "clipitem",
                                    id=f"a1_vo_{i+1}_{_uid()[:6]}")
        ET.SubElement(audio_item, "name").text = f"[VO] {vo_label}"
        # Duration in audio samples (frames × samples_per_frame)
        duration_samples = scene["duration_frames"] * (SAMPLE_RATE // FPS)
        ET.SubElement(audio_item, "duration").text = str(duration_samples)
        _rate_element(audio_item, FPS)
        ET.SubElement(audio_item, "start").text = str(scene["start_frame"])
        ET.SubElement(audio_item, "end").text = str(scene["end_frame"])
        ET.SubElement(audio_item, "in").text = "0"
        ET.SubElement(audio_item, "out").text = str(scene["duration_frames"])

        # Empty file reference — editor fills this with their audio
        a_file = ET.SubElement(audio_item, "file", id=f"afile_{i+1}_{_uid()[:6]}")
        ET.SubElement(a_file, "name").text = f"VO_Scene{i+1}"
        ET.SubElement(a_file, "pathurl").text = ""
        ET.SubElement(a_file, "duration").text = str(duration_samples)
        _rate_element(a_file, FPS)
        a_media_el = ET.SubElement(a_file, "media")
        a_audio_el = ET.SubElement(a_media_el, "audio")
        ET.SubElement(a_audio_el, "samplerate").text = str(SAMPLE_RATE)
        ET.SubElement(a_audio_el, "channelcount").text = str(AUDIO_CHANNELS)

        # Mark as stereo
        ET.SubElement(audio_item, "channelcount").text = str(AUDIO_CHANNELS)

    # ── Sequence-level markers (visual reference on timeline ruler) ───────────
    # These appear as coloured markers on the timeline so the editor can
    # quickly see scene boundaries and notes without opening clip properties.
    for i, scene in enumerate(parsed_scenes):
        marker = ET.SubElement(seq, "marker")
        ET.SubElement(marker, "name").text = f"Scene {scene.get('scene_id', i+1)}"
        ET.SubElement(marker, "comment").text = (
            f"Caption: {scene.get('caption', '')}\n"
            f"VO: {scene.get('voiceover', '')[:60]}..."
        )
        ET.SubElement(marker, "in").text = str(scene["start_frame"])
        ET.SubElement(marker, "out").text = str(scene["end_frame"])
        # Green marker colour (Premiere colour index 2 = green)
        ET.SubElement(marker, "color").text = "2"

    return root


# ─── SRT Generator ─────────────────────────────────────────────────────────────

def build_srt(scenes: list[dict]) -> str:
    """
    Generate a SubRip (.srt) subtitle file from scene captions.

    SRT format:
      [sequence number]
      [start] --> [end]
      [caption text]
      [blank line]

    Captions longer than 40 characters are word-wrapped to 2 lines
    to fit comfortably on a 1080px-wide vertical video frame.

    Args:
        scenes: List of scene dicts with timecode and caption fields.

    Returns:
        SRT file content as a string.
    """
    lines = []
    idx = 1

    for scene in scenes:
        caption = scene.get("caption", "").strip()
        if not caption:
            continue

        start_f, end_f = parse_timecode(scene["timecode"])
        start_ts = frames_to_srt_time(start_f)
        end_ts = frames_to_srt_time(end_f)

        # Word-wrap long captions to 2 lines for readability on vertical video
        if len(caption) > 40:
            wrapped = textwrap.fill(caption, width=40)
        else:
            wrapped = caption

        lines.append(str(idx))
        lines.append(f"{start_ts} --> {end_ts}")
        lines.append(wrapped)
        lines.append("")  # Blank line separator required by SRT spec
        idx += 1

    return "\n".join(lines)


# ─── Pretty-print XML ──────────────────────────────────────────────────────────

def prettify_xml(root: ET.Element) -> str:
    """
    Convert ET.Element tree to a nicely indented XML string.

    Uses minidom for pretty-printing since ElementTree doesn't support
    indentation until Python 3.9, and we want compatibility with 3.8+.
    The XML declaration is included at the top.
    """
    raw_string = ET.tostring(root, encoding="unicode", xml_declaration=False)
    # Wrap in XML declaration + DOCTYPE for Premiere compatibility
    reparsed = minidom.parseString(raw_string)
    pretty = reparsed.toprettyxml(indent="  ", encoding=None)
    # minidom adds its own declaration — replace with correct version/encoding
    lines = pretty.split("\n")
    if lines[0].startswith("<?xml"):
        lines[0] = '<?xml version="1.0" encoding="UTF-8"?>'
    return "\n".join(lines)


# ─── Input Parser ──────────────────────────────────────────────────────────────

def load_scenes_from_scripting_output(
    json_path: str,
    mode: str = "full_pipeline",
) -> tuple[str, list[dict]]:
    """
    Extract scenes from the Scripting Agent's comparison output JSON.

    Reads the specified mode's script from test_scripting_comparison_output.json
    and returns the project name and list of scene dicts.

    Args:
        json_path: Path to test_scripting_comparison_output.json.
        mode:      Which scripting mode to use: "no_history", "retrieval_only",
                   or "full_pipeline" (default — highest quality).

    Returns:
        Tuple of (project_name, scenes_list).

    Raises:
        KeyError: If the specified mode or script data is not found.
        FileNotFoundError: If the JSON file doesn't exist.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    topic = data.get("topic", "ViralHook_Script")

    # Sanitise topic for use as filename — remove non-alphanumeric chars
    project_name = re.sub(r"[^\w\s]", "", topic)
    project_name = re.sub(r"\s+", "_", project_name.strip())[:50]
    if not project_name:
        project_name = "ViralHook_Script"

    results = data.get("results", {})
    if mode not in results:
        available = list(results.keys())
        raise KeyError(
            f"Mode '{mode}' not found in results. "
            f"Available modes: {available}"
        )

    mode_data = results[mode]
    if "error" in mode_data and mode_data.get("error"):
        raise ValueError(
            f"Mode '{mode}' has an error: {mode_data['error']}. "
            f"Choose a different mode."
        )

    script = mode_data.get("script")
    if not script:
        raise KeyError(f"No script found for mode '{mode}'")

    scenes = script.get("scenes", [])
    if not scenes:
        raise ValueError(f"No scenes found in '{mode}' script")

    # Add scene_id if missing
    for i, scene in enumerate(scenes, 1):
        scene.setdefault("scene_id", i)

    print(f"[XMLExporter] Loaded {len(scenes)} scenes from mode='{mode}'")
    print(f"[XMLExporter] Project name: '{project_name}'")
    print(f"[XMLExporter] Script concept: '{script.get('concept_name', 'N/A')}'")

    return project_name, scenes


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Convert ViralHook Scripting Agent output to Premiere Pro XML + SRT"
    )
    parser.add_argument(
        "--input", "-i",
        default=str(Path(__file__).parent / "test_scripting_comparison_output.json"),
        help="Path to test_scripting_comparison_output.json (default: pipeline/ directory)",
    )
    parser.add_argument(
        "--mode", "-m",
        default="full_pipeline",
        choices=["no_history", "retrieval_only", "full_pipeline"],
        help="Which scripting mode to use (default: full_pipeline)",
    )
    parser.add_argument(
        "--all-modes", "-a",
        action="store_true",
        help="Generate XML + SRT for ALL three modes (useful for POC comparison)",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    modes_to_run = (
        ["no_history", "retrieval_only", "full_pipeline"]
        if args.all_modes
        else [args.mode]
    )

    for mode in modes_to_run:
        print(f"\n{'='*60}")
        print(f"  Generating XML/SRT for mode: {mode}")
        print(f"{'='*60}")

        try:
            project_name, scenes = load_scenes_from_scripting_output(
                args.input, mode
            )

            # Add mode suffix when generating multiple files
            if args.all_modes:
                output_stem = f"{project_name}_{mode}"
            else:
                output_stem = project_name

            # ── Generate XML ──────────────────────────────────────────────────
            print(f"\n[XMLExporter] Building Premiere Pro XML...")
            xml_root = build_xml(output_stem, scenes)
            xml_str = prettify_xml(xml_root)
            xml_path = OUTPUT_DIR / f"{output_stem}.xml"
            with open(xml_path, "w", encoding="utf-8") as f:
                f.write(xml_str)
            print(f"[XMLExporter] ✓ XML saved: {xml_path}")

            # ── Generate SRT ──────────────────────────────────────────────────
            print(f"[XMLExporter] Building SRT subtitle file...")
            srt_str = build_srt(scenes)
            srt_path = OUTPUT_DIR / f"{output_stem}.srt"
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(srt_str)
            print(f"[XMLExporter] ✓ SRT saved: {srt_path}")

            # ── Print summary ─────────────────────────────────────────────────
            print(f"\n  Timeline summary:")
            for scene in scenes:
                start_f, end_f = parse_timecode(scene["timecode"])
                duration_s = (end_f - start_f) / FPS
                print(f"    Scene {scene.get('scene_id', '?')} "
                      f"[{scene['timecode']}] "
                      f"({duration_s:.1f}s) — "
                      f"{scene.get('caption', '')[:40]}")

        except (FileNotFoundError, KeyError, ValueError) as e:
            print(f"\n  ERROR for mode '{mode}': {e}")
            if not args.all_modes:
                raise

    print(f"\n{'='*60}")
    print(f"  Output directory: {OUTPUT_DIR.resolve()}")
    print(f"  Files generated:")
    for f in sorted(OUTPUT_DIR.iterdir()):
        size_kb = f.stat().st_size / 1024
        print(f"    {f.name} ({size_kb:.1f} KB)")
    print(f"{'='*60}\n")
    print("  Import instructions:")
    print("  Premiere Pro: File → Import → select the .xml file")
    print("  DaVinci Resolve: File → Import Timeline → select the .xml file")
    print("  Subtitles: File → Import → select the .srt file")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
