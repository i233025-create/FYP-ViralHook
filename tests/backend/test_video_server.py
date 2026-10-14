"""
Tests for the /video/* endpoints. The Video Agent itself is replaced by a
stub, so no model, GPU or FFmpeg is needed. Skipped if httpx (needed by
FastAPI's TestClient) is not installed.
"""

import time

import pytest

pytest.importorskip("httpx")
from fastapi.testclient import TestClient

import server
from pipeline.video.style_plan import GENERIC
from pipeline.video.timeline import SceneTrack, Timeline, VoiceClip


@pytest.fixture
def client(monkeypatch, tmp_path):
    import pipeline.agents.video_agent as agent

    video = tmp_path / "final.mp4"
    video.write_bytes(b"fake mp4")

    def fake_generate(plan, profile, mode, job_id, title, on_step):
        on_step(4, "Fetching visual assets", "shot 1/1")
        scene = SceneTrack(scene_id=1, segment="HOOK", start=0, end=2, clip_idea="city", caption="HI",
                           voiceover="hello", voice=VoiceClip(path="v.wav", duration=1.5))
        timeline = Timeline(job_id=job_id, style=GENERIC, scenes=[scene])
        return {"video_path": str(video), "timeline": timeline, "seconds": 1.0,
                "evaluation": {"scores": {"style_fidelity": 0.9}}}

    monkeypatch.setattr(agent, "generate_video", fake_generate)
    monkeypatch.setattr(agent, "load_profile", lambda: {})
    return TestClient(server.app)


def _wait(client, job_id):
    for _ in range(100):
        job = client.get(f"/video/status/{job_id}").json()
        if job["status"] in ("done", "error"):
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_generate_poll_and_download(client, sample_production_plan):
    res = client.post("/video/generate", json={"plan": sample_production_plan})
    assert res.status_code == 200
    job = _wait(client, res.json()["jobId"])
    assert job["status"] == "done"
    assert job["timeline"][0]["segment"] == "HOOK"
    assert job["evaluation"]["scores"]["style_fidelity"] == 0.9
    assert "videoPath" not in job                      # no server paths leak to the browser
    assert client.get(job["videoUrl"]).content == b"fake mp4"


def test_rejects_bad_mode(client, sample_production_plan):
    res = client.post("/video/generate", json={"plan": sample_production_plan, "mode": "fancy"})
    assert res.status_code == 400


def test_rejects_empty_plan(client):
    assert client.post("/video/generate", json={"plan": {"scenes": []}}).status_code == 400


def test_unknown_job_404(client):
    assert client.get("/video/status/nope").status_code == 404
    assert client.get("/video/file/nope").status_code == 404
