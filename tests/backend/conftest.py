"""
conftest.py — Shared pytest fixtures for ViralHook backend tests.

All tests here are designed to run WITHOUT:
  - Groq API key
  - Whisper model download
  - CLIP model download
  - Internet access

This makes them safe to run in GitHub Actions CI.
API-dependent tests are marked with @pytest.mark.integration
and skipped in CI (no GROQ_API_KEY set).
"""

import sys
import os
from pathlib import Path
import pytest

# ── Add workspace root to sys.path ────────────────────────────────────────────
WORKSPACE_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))


# ── Markers ───────────────────────────────────────────────────────────────────
def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: marks tests that require API keys or models (skipped in CI)"
    )


# ── Skip integration tests if no API key ─────────────────────────────────────
def pytest_collection_modifyitems(config, items):
    has_groq_key = bool(os.getenv("GROQ_API_KEY", ""))
    skip_integration = pytest.mark.skip(
        reason="GROQ_API_KEY not set — skipping integration test"
    )
    for item in items:
        if "integration" in item.keywords and not has_groq_key:
            item.add_marker(skip_integration)


# ── Shared fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def sample_scenes():
    """5 scenes matching the mock script structure used throughout the app."""
    return [
        {
            "id": "s1", "startTime": "00:00", "endTime": "00:03",
            "segment": "HOOK",
            "voiceover": "AI won't replace developers. But developers who use AI will replace those who don't.",
            "caption": "AI WILL REPLACE DEVELOPERS?",
            "shot": "Close-up talking head",
            "visual": "Talking-head footage, direct eye contact",
        },
        {
            "id": "s2", "startTime": "00:03", "endTime": "00:08",
            "segment": "SETUP",
            "voiceover": "Everyone's debating whether AI takes our jobs. That's the wrong conversation entirely.",
            "caption": "WRONG QUESTION",
            "shot": "Medium shot",
            "visual": "B-roll: news headlines montage",
        },
        {
            "id": "s3", "startTime": "00:08", "endTime": "00:15",
            "segment": "MAIN POINT",
            "voiceover": "The real shift is this: AI agents are turning solo developers into one-person teams.",
            "caption": "ONE-PERSON TEAM",
            "shot": "Medium shot with gesture",
            "visual": "B-roll: developer coding with AI assistant",
        },
        {
            "id": "s4", "startTime": "00:15", "endTime": "00:22",
            "segment": "EVIDENCE",
            "voiceover": "GitHub Copilot users ship 55% more code.",
            "caption": "55% MORE OUTPUT",
            "shot": "Screen recording",
            "visual": "Screen: GitHub Copilot stats graphic",
        },
        {
            "id": "s5", "startTime": "00:22", "endTime": "00:27",
            "segment": "CONCLUSION",
            "voiceover": "The question is not will AI replace you. It is are you using AI yet?",
            "caption": "ARE YOU USING AI?",
            "shot": "Close-up, direct camera",
            "visual": "Return to talking head, confident close",
        },
    ]


@pytest.fixture
def sample_creator_profile():
    """Real creator_profile.json structure from Module 1 output."""
    return {
        "creator_niche": "Motivational self-improvement and personal growth",
        "signature_hooks": ["Contrarian", "Bold Claim", "Curiosity Gap"],
        "dominant_tone": "Inspirational",
        "avg_pacing": "Fast-paced",
        "typical_structure": "Hook → Explanation",
        "target_audience": "Young adults (18-35) seeking motivation and personal growth",
        "recurring_topics": [
            "Personal growth", "Mortality", "Daily life frustrations",
            "Consistency", "Motivational advice",
        ],
        "content_style_summary": (
            "Fast-paced and direct. Opens with a bold contrarian claim, "
            "delivers a concise practical takeaway."
        ),
        "visual_style_suggestions": [
            "Fast cuts and quick transitions",
            "On-screen text overlays highlighting key phrases",
        ],
    }


@pytest.fixture
def sample_production_plan(sample_scenes):
    """Production plan dict as used by the XML export endpoint."""
    return {
        "id": "pp_test",
        "title": "Will_AI_Replace_Programmers",
        "totalDuration": "00:27",
        "scenes": sample_scenes,
    }


# ── Signed-in clients for server.py (temporary DB + workspaces) ───────────────

@pytest.fixture
def make_user_client(tmp_path, monkeypatch):
    """
    Factory: make_user_client("a@example.com") → a TestClient for server.app,
    signed in as a fresh user. All users share one temporary database and a
    temporary data/users/ folder, so nothing touches the real data/.
    """
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    import server
    from backend import auth, workspace
    from backend.config import Settings
    from backend.db import get_db, make_engine, migrate
    from backend.mailer import ConsoleMailer

    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    migrate(url)
    engine = make_engine(url)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    settings = Settings(env="test", database_url=url, jwt_secret="t" * 48, cookie_secure=False,
                        allowed_origins=("http://localhost:5173",), frontend_url="http://localhost:5173")
    monkeypatch.setattr(workspace, "USERS_DIR", tmp_path / "users")

    def db_override():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    overrides = {get_db: db_override, auth.settings_dep: lambda: settings,
                 auth.mailer_dep: lambda: ConsoleMailer()}
    server.app.dependency_overrides.update(overrides)

    def make(email="creator@example.com", name="Creator"):
        client = TestClient(server.app)
        res = client.post("/auth/signup", json={"name": name, "email": email, "password": "test password 123"})
        assert res.status_code == 201, res.text
        client.user_id = res.json()["user"]["id"]
        return client

    yield make
    for key in overrides:
        server.app.dependency_overrides.pop(key, None)
    engine.dispose()
