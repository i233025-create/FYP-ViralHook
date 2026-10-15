"""
tone_analyzer.py — Measured brightness / colour of the creator's footage
=========================================================================
CLIP zero-shot ("dark moody" vs "bright high-key") judges lighting poorly on
stylised footage, so lighting is measured from pixels instead:

  brightness   mean luma (0 = black, 1 = white) over the sampled frames
  saturation   mean HSV saturation
  accent       most common hue among strongly saturated pixels (e.g. "purple"),
               the colour that pops on the creator's footage

pipeline/video/creator_visual.apply_measured_tone() turns these into SDXL
look words ("dark moody low-key lighting, purple neon accents").
"""

from __future__ import annotations

from collections import Counter

import numpy as np
from PIL import Image

MAX_FRAMES = 30
ACCENT_SAT, ACCENT_VAL = 0.45, 0.35        # "strongly saturated" pixel
MIN_ACCENT_SHARE = 0.02                    # of all pixels, for an accent to count

# Hue (degrees) → name, upper bounds
HUES = [(15, "red"), (40, "orange"), (65, "yellow"), (160, "green"), (195, "cyan"),
        (250, "blue"), (290, "purple"), (335, "pink"), (360, "red")]


def _hue_name(deg: float) -> str:
    return next(name for bound, name in HUES if deg < bound)


def measure_tone(frame_paths: list[str]) -> dict:
    if not frame_paths:
        return {}
    idx = np.linspace(0, len(frame_paths) - 1, min(MAX_FRAMES, len(frame_paths))).round().astype(int)
    lumas, sats, hues, total = [], [], Counter(), 0
    for i in sorted(set(idx)):
        img = Image.open(frame_paths[i]).convert("RGB")
        img.thumbnail((160, 160))
        rgb = np.asarray(img, dtype=np.float32) / 255.0
        hsv = np.asarray(img.convert("HSV"), dtype=np.float32) / 255.0
        lumas.append(float((rgb @ [0.299, 0.587, 0.114]).mean()))
        sats.append(float(hsv[..., 1].mean()))
        strong = (hsv[..., 1] > ACCENT_SAT) & (hsv[..., 2] > ACCENT_VAL)
        hues.update(_hue_name(h * 360) for h in hsv[..., 0][strong])
        total += strong.size
    accent = hues.most_common(1)
    return {
        "brightness": round(float(np.mean(lumas)), 4),
        "saturation": round(float(np.mean(sats)), 4),
        "accent_colour": accent[0][0] if accent and accent[0][1] / total >= MIN_ACCENT_SHARE else None,
        "hue_counts": dict(hues.most_common(4)),
    }


def aggregate_tone(per_video: list[dict]) -> dict:
    measured = [t for t in per_video if t and "brightness" in t]
    if not measured:
        return {}
    hues = Counter()
    for t in measured:
        hues.update(t.get("hue_counts", {}))
    accents = Counter(t["accent_colour"] for t in measured if t.get("accent_colour"))
    return {
        "mean_brightness": round(float(np.mean([t["brightness"] for t in measured])), 4),
        "mean_saturation": round(float(np.mean([t["saturation"] for t in measured])), 4),
        # The accent must recur: in at least half the videos
        "accent_colour": (accents.most_common(1)[0][0]
                          if accents and accents.most_common(1)[0][1] >= len(measured) / 2 else None),
    }
