"""
timeline.py — Typed video timeline (timeline.json)
===================================================
The timeline is the single source of truth between planning and rendering:
every later step (renderer, evaluator, frontend preview) reads only this.

Timing is audio-first: a scene lasts exactly as long as its synthesized
voiceover (+ a short pause), never as long as the LLM's guessed timecode.

  Timeline
   ├── style: StyleParams          (from style_plan.py)
   └── scenes: [SceneTrack]
         ├── voice: VoiceClip      (wav path + word timings, scene-relative)
         └── shots: [Shot]         (absolute start/end, query, Asset)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

FPS = 30
WIDTH = 1080
HEIGHT = 1920
MIN_SHOT_SECONDS = 0.8
END_TAIL_SECONDS = 0.5   # hold the last frame a moment after the final word

Motion = Literal["zoom_in", "zoom_out", "pan_left", "pan_right", "none"]
MOTION_CYCLE: list[str] = ["zoom_in", "pan_right", "zoom_out", "pan_left"]


# ─── Models ───────────────────────────────────────────────────────────────────

class StyleParams(BaseModel):
    """Edit parameters. Personalised values come from the creator profile."""
    mode: Literal["personalised", "generic"]
    shot_duration: float = Field(description="Target seconds per shot (cut rhythm)")
    target_wpm: Optional[float] = Field(
        default=None, description="Voiceover speech rate to hit; None = TTS default speed")
    zoom_strength: float = Field(description="Ken Burns zoom/pan amount, 0.0–0.3")
    caption_style: Literal["karaoke", "scene"]
    scene_gap: float = Field(description="Silence between scenes, seconds")
    visual_look: list[str] = Field(
        default_factory=list, description="Creator look words added to image prompts")
    creator_weight: float = Field(
        default=0.0, description="Weight of creator-look similarity when ranking shots")
    sources: dict = Field(default_factory=dict,
                          description="Which profile fields produced each value")


class WordTiming(BaseModel):
    word: str
    start: float
    end: float


class VoiceClip(BaseModel):
    path: str
    duration: float
    words: list[WordTiming] = Field(default_factory=list)
    speed: float = 1.0
    measured_wpm: Optional[float] = None


class Asset(BaseModel):
    path: str
    kind: Literal["video", "image"]
    source: Literal["pexels", "sdxl", "placeholder"]
    query: str
    clip_score: Optional[float] = None            # CLIP(asset, shot query)
    creator_score: Optional[float] = None         # CLIP(asset) · creator centroid
    source_id: Optional[str] = None
    note: str = ""


class Shot(BaseModel):
    start: float
    end: float
    query: str
    image_prompt: str = ""
    motion: Motion = "none"
    asset: Optional[Asset] = None

    @property
    def duration(self) -> float:
        return self.end - self.start


class SceneTrack(BaseModel):
    scene_id: int
    segment: str
    start: float
    end: float
    clip_idea: str
    caption: str
    voiceover: str
    voice: VoiceClip
    shots: list[Shot] = Field(default_factory=list)


class Timeline(BaseModel):
    job_id: str
    title: str = "ViralHook"
    fps: int = FPS
    width: int = WIDTH
    height: int = HEIGHT
    style: StyleParams
    scenes: list[SceneTrack]

    @property
    def duration(self) -> float:
        return self.scenes[-1].end if self.scenes else 0.0

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: str | Path) -> "Timeline":
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))


# ─── Script normalisation ─────────────────────────────────────────────────────

def _segment_for(index: int, total: int) -> str:
    if index == 0:
        return "HOOK"
    if index == total - 1 and total > 2:
        return "CONCLUSION"
    return "BODY"


def normalize_scenes(script) -> list[dict]:
    """
    Accept any script shape the project produces and return plain scene dicts
    {segment, clip_idea, caption, voiceover}:

      - ScriptOutput (pydantic) or its dict      — scenes[].clip_idea
      - frontend production plan {scenes: [...]} — scenes[].visual / .segment
      - a bare list of scenes
    """
    if hasattr(script, "model_dump"):
        script = script.model_dump()
    scenes = script.get("scenes", []) if isinstance(script, dict) else list(script or [])

    out = []
    for i, sc in enumerate(scenes):
        sc = sc.model_dump() if hasattr(sc, "model_dump") else dict(sc)
        voiceover = (sc.get("voiceover") or "").strip()
        if not voiceover:
            continue   # nothing to say → nothing to time this scene against
        out.append({
            "segment": sc.get("segment") or "",
            "clip_idea": (sc.get("clip_idea") or sc.get("visual") or sc.get("caption") or "").strip(),
            "caption": (sc.get("caption") or "").strip(),
            "voiceover": voiceover,
        })
    for i, sc in enumerate(out):
        sc["segment"] = sc["segment"] or _segment_for(i, len(out))
    if not out:
        raise ValueError("Script has no scenes with voiceover text.")
    return out


# ─── Timing ───────────────────────────────────────────────────────────────────

def layout_scenes(voice_durations: list[float], gap: float) -> list[tuple[float, float]]:
    """
    Back-to-back scene windows from the real voiceover lengths.
    Each scene = its audio + `gap` of silence; the last one gets a tail instead.
    """
    windows, t = [], 0.0
    for i, dur in enumerate(voice_durations):
        pad = END_TAIL_SECONDS if i == len(voice_durations) - 1 else gap
        end = round(t + dur + pad, 3)
        windows.append((round(t, 3), end))
        t = end
    return windows


def split_shots(start: float, end: float, shot_duration: float,
                min_shot: float = MIN_SHOT_SECONDS) -> list[tuple[float, float]]:
    """
    Cut a scene window into equal sub-shots as close to `shot_duration` as
    possible, never shorter than `min_shot`.
    """
    length = end - start
    n = max(1, round(length / max(shot_duration, 0.1)))
    while n > 1 and length / n < min_shot:
        n -= 1
    step = length / n
    bounds = [round(start + k * step, 3) for k in range(n)] + [round(end, 3)]
    return list(zip(bounds[:-1], bounds[1:]))


def motion_for(shot_index: int) -> str:
    return MOTION_CYCLE[shot_index % len(MOTION_CYCLE)]


def format_mmss(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def to_frontend(timeline: Timeline) -> list[dict]:
    """Scene list in the shape VideoGenScreen.jsx renders."""
    return [
        {
            "id": f"s{sc.scene_id}",
            "segment": sc.segment,
            "startTime": format_mmss(sc.start),
            "endTime": format_mmss(sc.end),
            "start": sc.start,
            "end": sc.end,
            "voiceover": sc.voiceover,
            "caption": sc.caption,
            "visual": sc.clip_idea,
            "shots": [
                {"start": sh.start, "end": sh.end, "query": sh.query,
                 "source": sh.asset.source if sh.asset else None,
                 "clipScore": sh.asset.clip_score if sh.asset else None,
                 "creatorScore": sh.asset.creator_score if sh.asset else None}
                for sh in sc.shots
            ],
        }
        for sc in timeline.scenes
    ]


def dump_json(data, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
