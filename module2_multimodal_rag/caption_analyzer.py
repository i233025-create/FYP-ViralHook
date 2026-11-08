"""
caption_analyzer.py — How the creator's burned-in captions look
================================================================
OCR (RapidOCR, ONNX on CPU) over the frames Module 2 already samples, then
measure the caption lines it finds:

  position     vertical centre of the caption (0 = top, 1 = bottom)
  size         line height as a fraction of frame height
  colour       median text-pixel colour, snapped to a named palette
  boxed        caption sits on a solid box (vs straight on the footage)
  uppercase    share of upper-case letters
  line length  letters per caption line (OCR drops spaces) → words per chunk
  accent mode  a second colour INSIDE a line = word highlight (karaoke);
               lines that are each one colour = whole-line accent

Which OCR boxes are captions: text that matches what is being said (the
transcript), horizontally centred, not code/UI-looking, and not a watermark
(the same text in many frames, e.g. "@handle"). Without a transcript only the
layout rules apply.

The Video Agent (pipeline/video/style_plan.py) turns the creator-level summary
into the ASS caption style, so captions are measured, not a fixed template.
"""

from __future__ import annotations

import re
from collections import Counter

import numpy as np
from PIL import Image

MAX_FRAMES = 30
MIN_CONFIDENCE = 0.6
CENTRE_TOLERANCE = 0.15        # |box centre x − 0.5| as a fraction of width
WATERMARK_SHARE = 0.3          # same text in ≥ 30 % of frames → watermark
SHINGLE = 5                    # letters per n-gram when matching OCR text to the transcript
MIN_SPOKEN = 0.6               # share of a line's n-grams that must occur in the transcript
CODE_CHARS = re.compile(r"[{}<>=/\\|;_]|\.(ts|js|py|tsx|jsx|json)\b")

PALETTE = {
    "white":  (245, 245, 245),
    "yellow": (250, 220, 40),
    "orange": (245, 145, 50),
    "red":    (230, 50, 50),
    "green":  (60, 200, 90),
    "cyan":   (60, 210, 230),
    "blue":   (60, 110, 240),
    "purple": (160, 90, 230),
    "pink":   (240, 110, 190),
    "black":  (20, 20, 20),
}

_ocr = None


def _get_ocr():
    global _ocr
    if _ocr is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr = RapidOCR()
    return _ocr


def _letters(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


def is_spoken(text: str, transcript_letters: str) -> bool:
    """OCR drops spaces and misreads letters, so compare letter n-grams."""
    letters = _letters(text)
    if len(letters) < SHINGLE:
        return letters in transcript_letters
    grams = [letters[i:i + SHINGLE] for i in range(len(letters) - SHINGLE + 1)]
    return sum(g in transcript_letters for g in grams) / len(grams) >= MIN_SPOKEN


_NAMES = list(PALETTE)
_RGB = np.array([PALETTE[n] for n in _NAMES], dtype=float)


def nearest_colour(rgb) -> str:
    rgb = np.asarray(rgb, dtype=float)
    return min(PALETTE, key=lambda n: float(np.sum((rgb - PALETTE[n]) ** 2)))


def _colour_shares(pixels: np.ndarray) -> Counter:
    """Share of pixels per palette colour (anti-aliased black edges ignored)."""
    names = np.argmin(((pixels[:, None, :] - _RGB[None]) ** 2).sum(-1), axis=1)
    counts = Counter(_NAMES[i] for i in names if _NAMES[i] != "black")
    total = sum(counts.values()) or 1
    return Counter({k: v / total for k, v in counts.items()})


def _measure_box(img: np.ndarray, x0: int, y0: int, x1: int, y1: int) -> dict | None:
    """Text colour and box/no-box for one caption line."""
    h, w = img.shape[:2]
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
    crop = img[y0:y1, x0:x1].reshape(-1, 3).astype(float)
    if len(crop) < 30:
        return None
    # Background = thin ring just inside the OCR box
    ring = np.concatenate([img[y0:y0 + 2, x0:x1].reshape(-1, 3), img[y1 - 2:y1, x0:x1].reshape(-1, 3),
                           img[y0:y1, x0:x0 + 2].reshape(-1, 3), img[y0:y1, x1 - 2:x1].reshape(-1, 3)]
                          ).astype(float)
    bg = np.median(ring, axis=0)
    dist = np.linalg.norm(crop - bg, axis=1)
    text_px = crop[dist > 60]
    if len(text_px) < 10:
        return None
    # Boxed: the ring is uniform and differs from what is just outside the box
    pad = max(4, (y1 - y0) // 2)
    outer = np.concatenate([img[max(0, y0 - pad):y0, x0:x1].reshape(-1, 3),
                            img[y1:min(h, y1 + pad), x0:x1].reshape(-1, 3)]).astype(float)
    boxed = bool(len(outer) and ring.std(axis=0).mean() < 18
                 and np.linalg.norm(np.median(outer, axis=0) - bg) > 40)
    shares = _colour_shares(text_px).most_common(2)
    # Two clearly different colours inside one line → a highlighted word
    mixed = len(shares) == 2 and shares[1][1] >= 0.2
    return {"colour": shares[0][0] if shares else nearest_colour(np.median(text_px, axis=0)),
            "boxed": boxed, "box_colour": nearest_colour(bg), "mixed": mixed}


def analyze_captions(frame_paths: list[str], transcript: str = "") -> dict:
    """
    Caption summary for one video. `caption_frame_ratio` 0 means no captions
    were found; the other fields are then None.
    """
    if not frame_paths:
        return {"caption_frame_ratio": 0.0, "frames_checked": 0}
    idx = np.linspace(0, len(frame_paths) - 1, min(MAX_FRAMES, len(frame_paths))).round().astype(int)
    frames = [frame_paths[i] for i in sorted(set(idx))]
    ocr = _get_ocr()
    spoken = _letters(transcript)

    per_frame = []                                  # (img, [(text, x0, y0, x1, y1)])
    seen = Counter()
    for path in frames:
        img = np.asarray(Image.open(path).convert("RGB"))
        result, _ = ocr(img)
        boxes = []
        for pts, text, conf in result or []:
            if float(conf) < MIN_CONFIDENCE or len(_letters(text)) < 3:
                continue
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            boxes.append((text, int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))))
        per_frame.append((img, boxes))
        seen.update({_letters(b[0]) for b in boxes})

    watermarks = {t for t, n in seen.items() if n >= max(2, WATERMARK_SHARE * len(frames))}
    lines, caption_frames = [], 0
    for img, boxes in per_frame:
        h, w = img.shape[:2]
        found = False
        for text, x0, y0, x1, y1 in boxes:
            if spoken and not is_spoken(text, spoken):
                continue
            if (_letters(text) in watermarks or CODE_CHARS.search(text)
                    or abs((x0 + x1) / 2 / w - 0.5) > CENTRE_TOLERANCE or (x1 - x0) > 0.95 * w):
                continue
            look = _measure_box(img, x0, y0, x1, y1)
            if look is None:
                continue
            letters = [c for c in text if c.isalpha()]
            lines.append({**look,
                          "y_center": (y0 + y1) / 2 / h,
                          "height_ratio": (y1 - y0) / h,
                          "upper": sum(c.isupper() for c in letters) / len(letters),
                          "chars": len(re.sub(r"[^A-Za-z0-9]", "", text))})
            found = True
        caption_frames += found

    summary = {"caption_frame_ratio": round(caption_frames / len(frames), 3),
               "frames_checked": len(frames), "lines_measured": len(lines),
               "matched_transcript": bool(spoken)}
    if not lines:
        return summary
    med = lambda k: round(float(np.median([ln[k] for ln in lines])), 4)  # noqa: E731
    summary.update({
        "y_center": med("y_center"),
        "height_ratio": med("height_ratio"),
        "uppercase_ratio": med("upper"),
        "chars_per_line": med("chars"),
        "boxed_ratio": round(sum(ln["boxed"] for ln in lines) / len(lines), 3),
        "mixed_colour_ratio": round(sum(ln["mixed"] for ln in lines) / len(lines), 3),
        "colour_counts": dict(Counter(ln["colour"] for ln in lines)),
        "box_colour_counts": dict(Counter(ln["box_colour"] for ln in lines if ln["boxed"])),
    })
    return summary


def aggregate_captions(per_video: list[dict]) -> dict:
    """Creator-level caption look from the per-video summaries."""
    with_caps = [v for v in per_video if v and v.get("lines_measured")]
    out = {
        "videos_with_captions": len(with_caps),
        "videos_checked": len([v for v in per_video if v]),
        "mean_caption_frame_ratio": round(float(np.mean(
            [v.get("caption_frame_ratio", 0.0) for v in per_video if v] or [0.0])), 3),
    }
    if not with_caps:
        return out
    colours, boxes = Counter(), Counter()
    for v in with_caps:
        colours.update(v.get("colour_counts", {}))
        boxes.update(v.get("box_colour_counts", {}))
    ranked = colours.most_common()
    total = sum(colours.values())
    out.update({
        key: round(float(np.median([v[key] for v in with_caps])), 4)
        for key in ("y_center", "height_ratio", "uppercase_ratio", "chars_per_line", "boxed_ratio",
                    "mixed_colour_ratio")
    })
    out["primary_colour"] = ranked[0][0]
    # A second colour counts as the creator's accent when it is ≥ 20 % of lines
    out["accent_colour"] = ranked[1][0] if len(ranked) > 1 and ranked[1][1] / total >= 0.2 else None
    out["accent_share"] = round(ranked[1][1] / total, 3) if out["accent_colour"] else 0.0
    out["box_colour"] = boxes.most_common(1)[0][0] if boxes else None
    out["colour_counts"] = dict(colours)
    return out
