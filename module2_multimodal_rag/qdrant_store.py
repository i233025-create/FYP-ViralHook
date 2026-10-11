"""
qdrant_store.py
===============
Qdrant in-memory vector store with named vectors.

Two vector spaces per document:
  "text"   — 384-dim (all-MiniLM-L6-v2 from transcript profile)
  "visual" — 512-dim (CLIP ViT-B/32 mean-pooled frames)

Named vectors allow searching each space independently then
fusing results — better than concatenation because text and
visual distances are not mixed in the same embedding space.

Payload (metadata) stored alongside vectors:
  video_id, video_path, shot_count, avg_shot_duration,
  cut_frequency, speech_rate_wpm, energy_variance,
  pause_density, hook_type, tone, structure, pacing_label,
  transcript_summary, key_phrases, target_audience
"""

from __future__ import annotations

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    ScoredPoint,
)
import uuid


# ── Dimensions ─────────────────────────────────────────────────────────────────
TEXT_DIM   = 384   # all-MiniLM-L6-v2
VISUAL_DIM = 512   # CLIP ViT-B/32

COLLECTION_NAME = "multimodal_profiles"


def create_client() -> QdrantClient:
    """
    Create an in-memory Qdrant client.
    No Docker, no persistence — data lives for the duration of the process.
    For mid eval this is sufficient; switch to QdrantClient(path=...) for persistence.
    """
    return QdrantClient(":memory:")


def init_collection(client: QdrantClient) -> None:
    """
    Create the multimodal_profiles collection with named vectors.
    Safe to call multiple times — skips if already exists.
    """
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME in existing:
        return

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            "text": VectorParams(
                size=TEXT_DIM,
                distance=Distance.COSINE,
            ),
            "visual": VectorParams(
                size=VISUAL_DIM,
                distance=Distance.COSINE,
            ),
        },
    )
    print(f"[QdrantStore] Collection '{COLLECTION_NAME}' created (in-memory).")


def store_video_profile(
    client: QdrantClient,
    video_id: str,
    text_vector: list[float],
    visual_vector: list[float],
    payload: dict,
) -> str:
    """
    Store one video's multimodal profile in Qdrant.

    Args:
        client:        Qdrant client.
        video_id:      Unique identifier for this video (e.g. filename stem).
        text_vector:   384-dim text embedding from transcript profile.
        visual_vector: 512-dim CLIP visual embedding.
        payload:       Metadata dict — all non-vector features.

    Returns:
        Point ID (UUID string) assigned to this document.
    """
    point_id = str(uuid.uuid4())

    # Add video_id to payload for retrieval identification
    payload["video_id"] = video_id

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(
                id=point_id,
                vector={
                    "text":   text_vector,
                    "visual": visual_vector,
                },
                payload=payload,
            )
        ],
    )

    print(f"[QdrantStore] Stored '{video_id}' → point {point_id[:8]}...")
    return point_id


def retrieve_similar(
    client: QdrantClient,
    query_text_vector: list[float],
    top_k: int = 3,
    use_visual: bool = False,
    query_visual_vector: list[float] | None = None,
) -> list[dict]:
    """
    Retrieve top-k most similar video profiles.

    Search strategy:
      - If use_visual=False: search text space only (fast, topic-based)
      - If use_visual=True: search both spaces, fuse with RRF

    Args:
        client:               Qdrant client.
        query_text_vector:    384-dim query embedding.
        top_k:                Number of results to return.
        use_visual:           Whether to include visual space search.
        query_visual_vector:  512-dim visual query vector (required if use_visual=True).

    Returns:
        List of dicts, each containing payload + scores, sorted by relevance.
    """
    count = client.count(collection_name=COLLECTION_NAME).count
    if count == 0:
        return []

    effective_k = min(top_k, count)

    # ── Text search ────────────────────────────────────────────────────────────
    text_response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_text_vector,
        using="text",
        limit=effective_k,
        with_payload=True,
    )
    text_results = text_response.points

    if not use_visual or query_visual_vector is None:
        return _format_results(text_results)

    # ── Visual search ──────────────────────────────────────────────────────────
    visual_response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_visual_vector,
        using="visual",
        limit=effective_k,
        with_payload=True,
    )
    visual_results = visual_response.points

    # ── RRF fusion ─────────────────────────────────────────────────────────────
    fused = _reciprocal_rank_fusion(text_results, visual_results, k=60)
    return fused[:effective_k]


def get_all_profiles(client: QdrantClient) -> list[dict]:
    """
    Return all stored video profiles (for dashboard display).
    Used by the frontend to show per-video analysis cards.
    """
    count = client.count(collection_name=COLLECTION_NAME).count
    if count == 0:
        return []

    results, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        limit=100,
        with_payload=True,
        with_vectors=False,
    )
    return [r.payload for r in results]


def _format_results(scored_points: list[ScoredPoint]) -> list[dict]:
    """Convert Qdrant ScoredPoint list to plain dicts."""
    out = []
    for p in scored_points:
        entry = dict(p.payload or {})
        entry["_score"] = round(p.score, 4)
        out.append(entry)
    return out


def _reciprocal_rank_fusion(
    text_results: list[ScoredPoint],
    visual_results: list[ScoredPoint],
    k: int = 60,
) -> list[dict]:
    """
    Reciprocal Rank Fusion (RRF) — standard multi-list fusion algorithm.

    RRF score = Σ 1 / (k + rank_i)  for each result list i

    k=60 is the standard RRF constant (Cormack et al. 2009).
    Higher k reduces the impact of high-ranking documents.

    Returns list of dicts sorted by descending RRF score.
    """
    scores: dict[str, float] = {}
    payloads: dict[str, dict] = {}

    for rank, point in enumerate(text_results, start=1):
        pid = str(point.id)
        scores[pid]   = scores.get(pid, 0.0) + 1.0 / (k + rank)
        payloads[pid] = dict(point.payload or {})

    for rank, point in enumerate(visual_results, start=1):
        pid = str(point.id)
        scores[pid]   = scores.get(pid, 0.0) + 1.0 / (k + rank)
        if pid not in payloads:
            payloads[pid] = dict(point.payload or {})

    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)

    result = []
    for pid in sorted_ids:
        entry = payloads[pid]
        entry["_score"]     = round(scores[pid], 6)
        entry["_fusion"]    = "rrf"
        result.append(entry)

    return result
