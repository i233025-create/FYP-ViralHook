"""
visual_embedder.py
==================
Generates visual features for a video using CLIP ViT-B/32:

  1. Frame embeddings  — 512-dim mean-pooled visual embedding
  2. talking_head_pct  — % of frames classified as "person talking to camera"
                         via CLIP zero-shot text-image similarity

Why CLIP zero-shot for talking_head_pct:
  Instead of training a classifier, we compare each frame embedding
  against text embeddings of two prompts:
    - "a person talking directly to camera, talking head video"
    - "b-roll footage, scenery, objects, no person talking"
  Whichever text prompt has higher cosine similarity wins.
  This gives us a free talking_head ratio with no labelled data.

Known limitation (temporal):
  Mean pooling loses temporal order — a fast-cut and slow-cut video
  with the same visual content get similar embeddings. Temporal patterns
  are handled separately via shot stats (cut_frequency, avg_shot_duration)
  in scene_detector.py. Future work: VideoMAE / TimeSformer for temporal
  video embeddings that preserve sequence order.

Output:
  get_visual_embedding()  → list[float] 512-dim
  get_talking_head_pct()  → float 0.0–1.0
"""

from __future__ import annotations

import torch
import numpy as np
from PIL import Image


# ── Module-level model + text embedding cache ─────────────────────────────────
_clip_model      = None
_clip_preprocess = None
_clip_device     = None
_text_embeddings = None   # cached text prompt embeddings for zero-shot


def _load_clip():
    """Load CLIP ViT-B/32 (cached after first call)."""
    global _clip_model, _clip_preprocess, _clip_device

    if _clip_model is not None:
        return _clip_model, _clip_preprocess, _clip_device

    import open_clip

    _clip_device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[VisualEmbedder] Loading CLIP ViT-B/32 on {_clip_device}...")

    _clip_model, _, _clip_preprocess = open_clip.create_model_and_transforms(
        "ViT-B-32",
        pretrained="openai",
    )
    _clip_model = _clip_model.to(_clip_device)
    _clip_model.eval()

    print("[VisualEmbedder] CLIP ready.")
    return _clip_model, _clip_preprocess, _clip_device


def _get_text_embeddings():
    """
    Compute and cache CLIP text embeddings for zero-shot classification.

    Two prompts:
      index 0 = talking head  (person speaking directly to camera)
      index 1 = b-roll        (no person, background/scenery footage)
    """
    global _text_embeddings

    if _text_embeddings is not None:
        return _text_embeddings

    import open_clip

    model, _, _ = _load_clip()

    prompts = [
        "a person talking directly to camera, talking head video, face visible",
        "b-roll footage, background scenery, objects, no person talking to camera",
    ]

    tokenizer = open_clip.get_tokenizer("ViT-B-32")
    tokens    = tokenizer(prompts).to(_clip_device)

    with torch.no_grad():
        text_feats = model.encode_text(tokens)
        text_feats = text_feats / text_feats.norm(dim=-1, keepdim=True)

    _text_embeddings = text_feats   # (2, 512)
    return _text_embeddings


def embed_frames(frame_paths: list[str], batch_size: int = 16) -> np.ndarray:
    """
    Embed frame images with CLIP ViT-B/32.

    Returns:
        np.ndarray (N, 512) — L2-normalised per-frame embeddings.
    """
    model, preprocess, device = _load_clip()

    all_embeddings = []

    for i in range(0, len(frame_paths), batch_size):
        batch_paths = frame_paths[i : i + batch_size]
        images = []
        for p in batch_paths:
            try:
                img = Image.open(p).convert("RGB")
                images.append(preprocess(img))
            except Exception as e:
                print(f"[VisualEmbedder] Skipping frame {p}: {e}")
                continue

        if not images:
            continue

        image_tensor = torch.stack(images).to(device)

        # Fixed: use torch.amp.autocast instead of deprecated torch.cuda.amp.autocast
        with torch.no_grad():
            if device == "cuda":
                with torch.amp.autocast("cuda"):
                    features = model.encode_image(image_tensor)
            else:
                features = model.encode_image(image_tensor)

            # autocast returns fp16 on CUDA; keep embeddings fp32 so they match
            # the fp32 text embeddings (zero-shot) and downstream numpy maths
            features = features.float()
            features = features / features.norm(dim=-1, keepdim=True)

        all_embeddings.append(features.cpu().numpy())

    if not all_embeddings:
        print("[VisualEmbedder] WARNING: No frames embedded, returning zero vector.")
        return np.zeros((1, 512), dtype=np.float32)

    return np.vstack(all_embeddings)   # (N, 512)


def classify_frames_talking_head(frame_embeddings: np.ndarray) -> float:
    """
    Zero-shot classify each frame as talking-head or b-roll using CLIP.

    For each frame embedding, compute cosine similarity against:
      [0] "person talking to camera"
      [1] "b-roll footage"

    talking_head_pct = fraction of frames where index 0 wins.

    Args:
        frame_embeddings: np.ndarray (N, 512) — from embed_frames().

    Returns:
        Float 0.0–1.0 — proportion of frames classified as talking head.
    """
    text_emb = _get_text_embeddings()   # (2, 512) on device

    # Move frame embeddings to same device as text embeddings
    frame_tensor = torch.from_numpy(frame_embeddings).to(_clip_device, text_emb.dtype)  # (N, 512)

    # Cosine similarity: frame_tensor @ text_emb.T → (N, 2)
    with torch.no_grad():
        sims = frame_tensor @ text_emb.T   # (N, 2)

    # For each frame, which prompt had higher similarity?
    predicted = sims.argmax(dim=-1).cpu().numpy()   # 0=talking_head, 1=broll

    talking_head_pct = float((predicted == 0).sum()) / len(predicted)
    return round(talking_head_pct, 4)


def mean_pool_embedding(frame_embeddings: np.ndarray) -> list[float]:
    """
    Mean-pool per-frame embeddings → single L2-normalised video vector.

    Returns:
        List of 512 floats.
    """
    pooled = frame_embeddings.mean(axis=0)
    norm   = np.linalg.norm(pooled)
    if norm > 0:
        pooled = pooled / norm
    return pooled.astype(np.float32).tolist()


def get_visual_embedding(frame_paths: list[str]) -> list[float]:
    """
    Full pipeline: frame paths → 512-dim visual embedding.
    """
    if not frame_paths:
        print("[VisualEmbedder] No frames provided, returning zero vector.")
        return [0.0] * 512

    frame_embeddings = embed_frames(frame_paths)
    return mean_pool_embedding(frame_embeddings)


def get_talking_head_pct(frame_paths: list[str]) -> float:
    """
    Full pipeline: frame paths → talking_head_pct (0.0–1.0).

    Reuses frame embeddings from embed_frames() — call get_visual_features()
    to compute both in one pass (avoids embedding frames twice).
    """
    if not frame_paths:
        return 0.0
    frame_embeddings = embed_frames(frame_paths)
    return classify_frames_talking_head(frame_embeddings)


def get_visual_features(frame_paths: list[str]) -> dict:
    """
    Compute both visual embedding AND talking_head_pct in one pass.
    Avoids running CLIP twice on the same frames.

    Returns:
        {
          "visual_vector":    list[float] 512-dim,
          "talking_head_pct": float 0.0-1.0,
          "broll_pct":        float 0.0-1.0,
        }
    """
    if not frame_paths:
        return {
            "visual_vector":    [0.0] * 512,
            "talking_head_pct": 0.0,
            "broll_pct":        1.0,
        }

    frame_embeddings     = embed_frames(frame_paths)
    visual_vector        = mean_pool_embedding(frame_embeddings)
    talking_head_pct     = classify_frames_talking_head(frame_embeddings)

    return {
        "visual_vector":    visual_vector,
        "talking_head_pct": talking_head_pct,
        "broll_pct":        round(1.0 - talking_head_pct, 4),
    }
