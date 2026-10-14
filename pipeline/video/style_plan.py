"""
style_plan.py — Creator profile → edit parameters
==================================================
Turns the *measured* parts of the multimodal creator profile (Module 2) into
concrete editing decisions, so the video is cut, paced and captioned the way
this creator's own videos are:

  profile field                                  → StyleParams
  visual_analysis.mean_avg_shot_duration (1.84s) → shot_duration
  audio_analysis.mean_speech_rate_wpm   (127)    → target_wpm (TTS speed)
  audio_analysis.energy_label                    → zoom_strength
  audio_analysis.mean_pause_density              → scene_gap
  visual_style_suggestions mention text/captions → caption_style = karaoke
  Module 2 CLIP vectors (creator_visual.py)      → visual_look + creator_weight

The GENERIC baseline uses fixed template-editor defaults and ignores the
profile entirely. Comparing the two in evaluator.py is the ablation that shows
personalisation measurably changes the output.
"""

from __future__ import annotations

from .timeline import StyleParams

GENERIC = StyleParams(
    mode="generic",
    shot_duration=4.0,
    target_wpm=None,
    zoom_strength=0.04,
    caption_style="scene",
    scene_gap=0.4,
    sources={"all": "fixed template defaults (profile ignored)"},
)

# Fallbacks when the profile only has Module 1's text labels
PACING_LABEL_SHOT_SECONDS = {
    "very fast": 1.8,
    "fast": 2.5,
    "moderate": 4.0,
    "slow": 6.0,
}
ENERGY_ZOOM = {
    "highly dynamic": 0.12,
    "moderately dynamic": 0.08,
    "flat": 0.04,
}
CAPTION_HINTS = ("text", "caption", "subtitle", "overlay", "kinetic")
# rank = clip_text + CREATOR_WEIGHT · clip_creator (assets.py). Text scores between
# candidates differ by ~0.03 and creator scores by ~0.05, so 0.5 lets the creator's
# look break ties between on-topic shots without overriding the topic.
CREATOR_WEIGHT = 0.5


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _shot_duration(profile: dict, sources: dict) -> float:
    measured = (profile.get("visual_analysis") or {}).get("mean_avg_shot_duration")
    if measured:
        sources["shot_duration"] = f"visual_analysis.mean_avg_shot_duration={measured}"
        return round(_clamp(float(measured), 1.0, 8.0), 3)
    label = (profile.get("avg_pacing") or "").lower()
    for key, seconds in PACING_LABEL_SHOT_SECONDS.items():
        if key in label:
            sources["shot_duration"] = f"avg_pacing='{profile.get('avg_pacing')}' (label fallback)"
            return seconds
    sources["shot_duration"] = "default (no pacing in profile)"
    return GENERIC.shot_duration


def _target_wpm(profile: dict, sources: dict):
    measured = (profile.get("audio_analysis") or {}).get("mean_speech_rate_wpm")
    if measured:
        sources["target_wpm"] = f"audio_analysis.mean_speech_rate_wpm={measured}"
        return round(_clamp(float(measured), 90.0, 200.0), 1)
    sources["target_wpm"] = "none in profile → TTS default speed"
    return None


def _zoom_strength(profile: dict, sources: dict) -> float:
    label = ((profile.get("audio_analysis") or {}).get("energy_label") or "").lower()
    for key, zoom in ENERGY_ZOOM.items():
        if key in label:
            sources["zoom_strength"] = f"audio_analysis.energy_label='{label}'"
            return zoom
    sources["zoom_strength"] = "default"
    return 0.08


def _scene_gap(profile: dict, sources: dict) -> float:
    density = (profile.get("audio_analysis") or {}).get("mean_pause_density")
    if density is not None:
        sources["scene_gap"] = f"audio_analysis.mean_pause_density={density}"
        return round(_clamp(0.1 + 2.0 * float(density), 0.1, 0.6), 3)
    sources["scene_gap"] = "default"
    return 0.25


def _caption_style(profile: dict, sources: dict) -> str:
    hints = " ".join(profile.get("visual_style_suggestions") or []).lower()
    if any(h in hints for h in CAPTION_HINTS):
        sources["caption_style"] = "visual_style_suggestions mention on-screen text"
        return "karaoke"
    sources["caption_style"] = "no text-overlay hint in profile"
    return "scene"


def plan_style(profile: dict | None, mode: str = "personalised",
               visual_look: list[str] | None = None, has_creator_visual: bool = False) -> StyleParams:
    """
    Return the edit parameters for `mode` ('personalised' or 'generic').
    `visual_look` / `has_creator_visual` come from creator_visual.py (Module 2 vectors).
    """
    if mode == "generic":
        return GENERIC.model_copy(deep=True)
    if mode != "personalised":
        raise ValueError(f"Unknown video mode: {mode!r}")

    profile = profile or {}
    sources: dict = {}
    if has_creator_visual:
        sources["visual_look"] = "CLIP zero-shot on Module 2 creator video vectors"
        sources["creator_weight"] = "Module 2 creator CLIP centroid available"
    else:
        sources["visual_look"] = sources["creator_weight"] = "no Module 2 visual vectors"
    return StyleParams(
        mode="personalised",
        shot_duration=_shot_duration(profile, sources),
        target_wpm=_target_wpm(profile, sources),
        zoom_strength=_zoom_strength(profile, sources),
        caption_style=_caption_style(profile, sources),
        scene_gap=_scene_gap(profile, sources),
        visual_look=list(visual_look or []) if has_creator_visual else [],
        creator_weight=CREATOR_WEIGHT if has_creator_visual else 0.0,
        sources=sources,
    )
