"""
multimodal_profiler.py
======================
Orchestrates the full multimodal pipeline for a single video.

Pipeline per video:
  1. Whisper transcription          (reused from module1)
  2. LLM text profile extraction    (reused from module1)
  3. Text embedding                 (all-MiniLM-L6-v2)
  4. Frame extraction               (FFmpeg, 1fps)
  5. CLIP visual embedding          (ViT-B/32, mean pooled → 512-dim)
  6. Shot detection                 (PySceneDetect)
  7. Audio feature extraction       (librosa)
  8. Store in Qdrant                (named vectors: text + visual)

Returns a rich per-video profile dict combining all modalities.
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

# ── Add workspace root to path so module1 imports work ────────────────────────
_MODULE2_DIR   = Path(__file__).parent.resolve()
_WORKSPACE_ROOT = _MODULE2_DIR.parent.resolve()
if str(_WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE_ROOT))

from module2_multimodal_rag.frame_extractor import (
    extract_frames,
    cleanup_frames,
    get_video_duration,
)
from module2_multimodal_rag.visual_embedder import get_visual_features
from module2_multimodal_rag.caption_analyzer import analyze_captions, aggregate_captions
from module2_multimodal_rag.tone_analyzer import measure_tone, aggregate_tone
from module2_multimodal_rag.scene_detector import (
    extract_shot_features,
    interpret_pacing,
)
from module2_multimodal_rag.audio_analyzer import (
    extract_audio_features,
    interpret_speech_rate,
    interpret_energy,
)
from module2_multimodal_rag.qdrant_store import store_video_profile


def process_video(
    video_path: str,
    video_index: int,
    total_videos: int,
    qdrant_client,
    groq_api_key: str,
    whisper_model_size: str = "tiny",
    verbose: bool = True,
) -> dict:
    """
    Run the full multimodal pipeline on a single video.

    Args:
        video_path:         Path to the video file.
        video_index:        1-based index (for display).
        total_videos:       Total number of videos being processed.
        qdrant_client:      Initialised Qdrant client.
        groq_api_key:       Groq API key for LLM profile extraction.
        whisper_model_size: Whisper model size ('tiny', 'base', 'small').
        verbose:            Print progress.

    Returns:
        Dict containing all extracted features + vectors for this video.
    """
    video_path = Path(video_path)
    video_id   = video_path.stem[:20]   # shortened for readable logs
    prefix     = f"[Vid {video_index}/{total_videos}] {video_id}"

    if verbose:
        print(f"\n{'─'*60}")
        print(f"{prefix} — Starting multimodal pipeline")

    result = {
        "video_id":    video_id,
        "video_path":  str(video_path),
        "transcript":        "",
        "text_profile":      {},
        "text_vector":       [],
        "visual_vector":     [],
        "talking_head_pct":  0.0,
        "broll_pct":         1.0,
        "shot_features":     {},
        "audio_features":    {},
        "caption_analysis":  {},
        "tone":              {},
        "errors":            [],
    }

    # ── Branch 1: Transcription + Text Profile (module1) ─────────────────────
    if verbose:
        print(f"{prefix} [1/5] Transcribing...")
    try:
        from module1_style_extraction.transcriber import process_local_video
        from module1_style_extraction.video_profiler import (
            create_video_profiler_chain,
            extract_video_profile,
        )
        from langchain_community.embeddings import HuggingFaceEmbeddings

        transcript = process_local_video(
            video_path=str(video_path),
            video_index=video_index,
            total=total_videos,
            model_size=whisper_model_size,
            language=None,
            task="translate",
        )
        result["transcript"] = transcript

        # Print transcript snippet for debugging transcription quality
        snippet = transcript[:200].replace('\n', ' ')
        print(f"{prefix} Transcript snippet: \"{snippet}...\"")

        if verbose:
            print(f"{prefix} [2/5] Extracting text profile...")

        chain        = create_video_profiler_chain(groq_api_key)
        text_profile = extract_video_profile(
            chain=chain,
            transcript=transcript,
            video_url=str(video_path),
            max_retries=2,
        )
        result["text_profile"] = text_profile

        # Text embedding
        embedder   = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        profile_str = _profile_to_string(text_profile)
        text_vector = embedder.embed_query(profile_str)
        result["text_vector"] = text_vector

    except Exception as e:
        msg = f"Text branch failed: {e}"
        result["errors"].append(msg)
        print(f"{prefix} ERROR — {msg}")
        # Use zero vector as fallback
        result["text_vector"] = [0.0] * 384

    # ── Branch 2: Visual Features (CLIP) ──────────────────────────────────────
    if verbose:
        print(f"{prefix} [3/5] Extracting visual features (CLIP + zero-shot)...")
    frame_paths, temp_dir = [], None
    try:
        frame_paths, temp_dir = extract_frames(str(video_path), fps=1.0, max_frames=60)
        visual_feats = get_visual_features(frame_paths)
        result["visual_vector"]    = visual_feats["visual_vector"]
        result["talking_head_pct"] = visual_feats["talking_head_pct"]
        result["broll_pct"]        = visual_feats["broll_pct"]
        print(f"{prefix} Talking head: {visual_feats['talking_head_pct']*100:.0f}% | "
              f"B-roll: {visual_feats['broll_pct']*100:.0f}%")
    except Exception as e:
        msg = f"Visual branch failed: {e}"
        result["errors"].append(msg)
        print(f"{prefix} ERROR — {msg}")
        result["visual_vector"] = [0.0] * 512

    # Captions and brightness/colour are measured on the same frames
    try:
        if frame_paths:
            result["tone"] = measure_tone(frame_paths)
            print(f"{prefix} Tone: brightness {result['tone']['brightness']:.2f} | "
                  f"accent {result['tone']['accent_colour']}")
            result["caption_analysis"] = analyze_captions(frame_paths, result.get("transcript", ""))
            ca = result["caption_analysis"]
            print(f"{prefix} Captions: {ca['caption_frame_ratio']*100:.0f}% of frames"
                  + (f" | {ca['colour_counts']} at y={ca['y_center']:.2f}" if ca.get("lines_measured") else ""))
    except Exception as e:
        msg = f"Caption/tone analysis failed: {e}"
        result["errors"].append(msg)
        print(f"{prefix} ERROR — {msg}")
    finally:
        if temp_dir:
            cleanup_frames(temp_dir)

    # ── Branch 3: Shot Detection ───────────────────────────────────────────────
    if verbose:
        print(f"{prefix} [4/5] Detecting shots...")
    try:
        shot_features = extract_shot_features(str(video_path))
        result["shot_features"] = shot_features
    except Exception as e:
        msg = f"Shot detection failed: {e}"
        result["errors"].append(msg)
        print(f"{prefix} ERROR — {msg}")
        result["shot_features"] = {
            "shot_count": 1, "avg_shot_duration": 30.0,
            "cut_frequency": 0.03, "min_shot_duration": 30.0,
            "max_shot_duration": 30.0, "total_duration": 30.0,
        }

    # ── Branch 4: Audio Features ───────────────────────────────────────────────
    if verbose:
        print(f"{prefix} [5/5] Analysing audio...")
    try:
        audio_features = extract_audio_features(
            video_path=str(video_path),
            transcript=result.get("transcript", ""),
            video_duration=result["shot_features"].get("total_duration", 0.0),
        )
        result["audio_features"] = audio_features
    except Exception as e:
        msg = f"Audio analysis failed: {e}"
        result["errors"].append(msg)
        print(f"{prefix} ERROR — {msg}")
        result["audio_features"] = {
            "speech_rate_wpm": 120.0, "energy_variance": 0.01,
            "pause_density": 0.2, "avg_energy": 0.05,
            "tempo": 120.0, "duration_seconds": 30.0,
        }

    # ── Build Qdrant payload ───────────────────────────────────────────────────
    sf = result["shot_features"]
    af = result["audio_features"]
    tp = result["text_profile"]

    payload = {
        # Identity
        "video_id":          video_id,
        "video_path":        str(video_path),
        # Text profile fields
        "hook_type":         tp.get("hook_type", "Unknown"),
        "tone":              tp.get("tone", "Unknown"),
        "structure":         tp.get("structure", "Unknown"),
        "key_phrases":       tp.get("key_phrases", []),
        "target_audience":   tp.get("target_audience", ""),
        "transcript_summary": tp.get("summary", ""),
        # Shot / visual features
        "shot_count":        sf.get("shot_count", 1),
        "avg_shot_duration": sf.get("avg_shot_duration", 30.0),
        "cut_frequency":     sf.get("cut_frequency", 0.03),
        "min_shot_duration": sf.get("min_shot_duration", 30.0),
        "max_shot_duration": sf.get("max_shot_duration", 30.0),
        "visual_pacing":     interpret_pacing(sf.get("avg_shot_duration", 30.0)),
        "talking_head_pct":  result.get("talking_head_pct", 0.0),
        "broll_pct":         result.get("broll_pct", 1.0),
        # Audio features
        "speech_rate_wpm":   af.get("speech_rate_wpm", 120.0),
        "energy_variance":   af.get("energy_variance", 0.01),
        "pause_density":     af.get("pause_density", 0.2),
        "avg_energy":        af.get("avg_energy", 0.05),
        "speech_rate_label": interpret_speech_rate(af.get("speech_rate_wpm", 120.0)),
        "energy_label":      interpret_energy(af.get("energy_variance", 0.01)),
        "caption_analysis":  result["caption_analysis"],
        "visual_tone":       result["tone"],
    }

    result["payload"] = payload

    # ── Store in Qdrant ────────────────────────────────────────────────────────
    try:
        point_id = store_video_profile(
            client=qdrant_client,
            video_id=video_id,
            text_vector=result["text_vector"],
            visual_vector=result["visual_vector"],
            payload=payload,
        )
        result["point_id"] = point_id
    except Exception as e:
        msg = f"Qdrant storage failed: {e}"
        result["errors"].append(msg)
        print(f"{prefix} ERROR — {msg}")

    if verbose:
        status = "✓" if not result["errors"] else f"⚠ {len(result['errors'])} error(s)"
        print(f"{prefix} Complete — {status}")
        print(f"  Shots: {sf.get('shot_count')} | "
              f"Avg shot: {sf.get('avg_shot_duration'):.1f}s | "
              f"Speech: {af.get('speech_rate_wpm'):.0f}wpm | "
              f"Pacing: {payload['visual_pacing']} | "
              f"Talking head: {result.get('talking_head_pct', 0)*100:.0f}%")

    return result


def build_multimodal_creator_profile(
    all_video_results: list[dict],
    qdrant_client,
    groq_api_key: str,
    creator_niche: str = "",
) -> dict:
    """
    Synthesise a master creator profile from all processed videos.

    Extends module1's text-only master profile with multimodal statistics:
      - Average shot count, pacing, speech rate across all videos
      - Dominant visual style patterns
      - Consistent audio delivery characteristics

    Args:
        all_video_results: List of per-video result dicts from process_video().
        qdrant_client:     Qdrant client (for RAG retrieval context).
        groq_api_key:      Groq API key.
        creator_niche:     Creator's content niche.

    Returns:
        Enhanced creator profile dict (superset of module1 profile).
    """
    if not all_video_results:
        return {}

    # ── Aggregate visual + audio stats across all videos ──────────────────────
    shot_counts    = [r["shot_features"].get("shot_count", 1)         for r in all_video_results]
    avg_shots      = [r["shot_features"].get("avg_shot_duration", 30) for r in all_video_results]
    cut_freqs      = [r["shot_features"].get("cut_frequency", 0.03)   for r in all_video_results]
    speech_rates   = [r["audio_features"].get("speech_rate_wpm", 120) for r in all_video_results]
    energy_vars    = [r["audio_features"].get("energy_variance", 0.01)for r in all_video_results]
    pause_dens     = [r["audio_features"].get("pause_density", 0.2)   for r in all_video_results]

    def _avg(lst):
        return round(sum(lst) / len(lst), 3) if lst else 0.0

    mean_shot_count   = _avg(shot_counts)
    mean_avg_shot_dur = _avg(avg_shots)
    mean_cut_freq     = _avg(cut_freqs)
    mean_speech_rate  = _avg(speech_rates)
    mean_energy_var   = _avg(energy_vars)
    mean_pause_den    = _avg(pause_dens)

    # ── Build text-only profile via module1 RAG ────────────────────────────────
    # Reuse module1's creator_profiler to get the text-based master profile
    text_master_profile = {}
    try:
        from module1_style_extraction.vector_store import initialize_vector_store, get_retriever
        from module1_style_extraction.creator_profiler import (
            create_creator_profile_chain,
            build_creator_profile,
        )

        # Use module1's ChromaDB if it has data
        chroma_path = str(_WORKSPACE_ROOT / "module1_style_extraction" / "chroma_db")
        vector_store = initialize_vector_store(chroma_path, "video_profiles")
        retriever    = get_retriever(vector_store, k=3)
        chain        = create_creator_profile_chain(groq_api_key)

        text_master_profile = build_creator_profile(
            retriever=retriever,
            chain=chain,
            query="Analyze the content style, tone, pacing, and hook strategies of this creator.",
            max_retries=2,
        )
    except Exception as e:
        print(f"[MultimodalProfiler] Text master profile failed: {e}")

    # ── Merge text + multimodal stats ──────────────────────────────────────────
    multimodal_profile = {
        **text_master_profile,   # all text-based fields from module1

        # Multimodal extensions
        "visual_analysis": {
            "mean_shot_count":        mean_shot_count,
            "mean_avg_shot_duration": mean_avg_shot_dur,
            "mean_cut_frequency":     mean_cut_freq,
            "visual_pacing":          interpret_pacing(mean_avg_shot_dur),
            "videos_analysed":        len(all_video_results),
            **aggregate_tone([r.get("tone") for r in all_video_results]),
        },
        "audio_analysis": {
            "mean_speech_rate_wpm": mean_speech_rate,
            "speech_rate_label":    interpret_speech_rate(mean_speech_rate),
            "mean_energy_variance": mean_energy_var,
            "energy_label":         interpret_energy(mean_energy_var),
            "mean_pause_density":   mean_pause_den,
        },
        "caption_analysis": aggregate_captions([r.get("caption_analysis") for r in all_video_results]),
        "per_video_profiles": [
            {
                "video_id":       r["payload"].get("video_id"),
                "hook_type":      r["payload"].get("hook_type"),
                "tone":           r["payload"].get("tone"),
                "structure":      r["payload"].get("structure"),
                "visual_pacing":  r["payload"].get("visual_pacing"),
                "shot_count":     r["payload"].get("shot_count"),
                "talking_head_pct": r["payload"].get("talking_head_pct", 0.0),
                "broll_pct":      r["payload"].get("broll_pct", 1.0),
                "speech_rate_wpm":r["payload"].get("speech_rate_wpm"),
                "key_phrases":    r["payload"].get("key_phrases", []),
                "errors":         r.get("errors", []),
            }
            for r in all_video_results
        ],
        "_module": "multimodal_rag_v1",
        "_analyzed_videos": len(all_video_results),
    }

    return multimodal_profile


def _profile_to_string(profile: dict) -> str:
    """
    Convert a per-video text profile dict to a string for embedding.
    Mirrors module1's approach.
    """
    parts = []
    if profile.get("hook_type"):
        parts.append(f"Hook type: {profile['hook_type']}")
    if profile.get("tone"):
        parts.append(f"Tone: {profile['tone']}")
    if profile.get("structure"):
        parts.append(f"Structure: {profile['structure']}")
    if profile.get("key_phrases"):
        phrases = ", ".join(profile["key_phrases"][:5])
        parts.append(f"Key phrases: {phrases}")
    if profile.get("target_audience"):
        parts.append(f"Target audience: {profile['target_audience']}")
    if profile.get("summary"):
        parts.append(f"Summary: {profile['summary']}")
    return " | ".join(parts) if parts else "Creator video profile"
