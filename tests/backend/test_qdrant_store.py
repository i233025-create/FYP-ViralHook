"""
test_qdrant_store.py
====================
Tests for module2_multimodal_rag/qdrant_store.py

Verifies Qdrant in-memory store creation, insertion,
retrieval, and RRF fusion without any external dependencies.
No API keys, no models required.
"""

import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.resolve()))

from module2_multimodal_rag.qdrant_store import (
    create_client,
    init_collection,
    store_video_profile,
    retrieve_similar,
    get_all_profiles,
    COLLECTION_NAME,
    TEXT_DIM,
    VISUAL_DIM,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _zero_text():
    return [0.0] * TEXT_DIM

def _zero_visual():
    return [0.0] * VISUAL_DIM

def _ones_text():
    v = [1.0] * TEXT_DIM
    norm = sum(x**2 for x in v) ** 0.5
    return [x / norm for x in v]

def _ones_visual():
    v = [1.0] * VISUAL_DIM
    norm = sum(x**2 for x in v) ** 0.5
    return [x / norm for x in v]


@pytest.fixture
def client():
    """Fresh in-memory Qdrant client per test."""
    c = create_client()
    init_collection(c)
    return c


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestClientAndCollection:

    def test_create_client_returns_client(self):
        c = create_client()
        assert c is not None

    def test_init_collection_creates_collection(self):
        c = create_client()
        init_collection(c)
        names = [col.name for col in c.get_collections().collections]
        assert COLLECTION_NAME in names

    def test_init_collection_idempotent(self):
        """Calling init_collection twice should not raise."""
        c = create_client()
        init_collection(c)
        init_collection(c)   # second call — should not crash
        names = [col.name for col in c.get_collections().collections]
        assert COLLECTION_NAME in names


class TestStoreProfile:

    def test_store_returns_point_id(self, client):
        pid = store_video_profile(
            client, "video1", _ones_text(), _ones_visual(),
            {"hook_type": "Contrarian", "tone": "Inspirational"},
        )
        assert isinstance(pid, str)
        assert len(pid) > 0

    def test_store_increments_count(self, client):
        store_video_profile(client, "v1", _ones_text(), _ones_visual(), {})
        store_video_profile(client, "v2", _zero_text(), _zero_visual(), {})
        count = client.count(collection_name=COLLECTION_NAME).count
        assert count == 2

    def test_payload_stored_correctly(self, client):
        store_video_profile(
            client, "v1", _ones_text(), _ones_visual(),
            {"hook_type": "Bold Claim", "speech_rate_wpm": 142.0},
        )
        profiles = get_all_profiles(client)
        assert len(profiles) == 1
        assert profiles[0]["hook_type"] == "Bold Claim"
        assert profiles[0]["speech_rate_wpm"] == 142.0

    def test_video_id_in_payload(self, client):
        store_video_profile(client, "my_video", _ones_text(), _ones_visual(), {})
        profiles = get_all_profiles(client)
        assert profiles[0]["video_id"] == "my_video"


class TestRetrieveSimilar:

    def test_retrieve_returns_list(self, client):
        store_video_profile(client, "v1", _ones_text(), _ones_visual(), {})
        results = retrieve_similar(client, _ones_text(), top_k=1)
        assert isinstance(results, list)

    def test_retrieve_correct_count(self, client):
        for i in range(3):
            store_video_profile(client, f"v{i}", _ones_text(), _ones_visual(), {})
        results = retrieve_similar(client, _ones_text(), top_k=3)
        assert len(results) == 3

    def test_retrieve_top_k_capped_at_stored(self, client):
        store_video_profile(client, "v1", _ones_text(), _ones_visual(), {})
        results = retrieve_similar(client, _ones_text(), top_k=10)
        assert len(results) == 1   # only 1 stored

    def test_retrieve_empty_store_returns_empty(self, client):
        results = retrieve_similar(client, _ones_text(), top_k=3)
        assert results == []

    def test_retrieve_results_have_score(self, client):
        store_video_profile(client, "v1", _ones_text(), _ones_visual(), {})
        results = retrieve_similar(client, _ones_text(), top_k=1)
        assert "_score" in results[0]

    def test_retrieve_with_visual_uses_rrf(self, client):
        store_video_profile(client, "v1", _ones_text(), _ones_visual(),
                            {"hook_type": "Contrarian"})
        results = retrieve_similar(
            client, _ones_text(), top_k=1,
            use_visual=True, query_visual_vector=_ones_visual(),
        )
        assert len(results) == 1
        assert results[0]["hook_type"] == "Contrarian"


class TestGetAllProfiles:

    def test_returns_all_stored(self, client):
        store_video_profile(client, "v1", _ones_text(), _ones_visual(), {"x": 1})
        store_video_profile(client, "v2", _ones_text(), _ones_visual(), {"x": 2})
        profiles = get_all_profiles(client)
        assert len(profiles) == 2

    def test_empty_store_returns_empty(self, client):
        profiles = get_all_profiles(client)
        assert profiles == []
