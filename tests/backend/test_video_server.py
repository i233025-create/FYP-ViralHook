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

    calls = []

    def fake_generate(plan, profile, mode, job_id, title, on_step, assets=None, scene_assets=None):
        calls.append({"assets": assets, "scene_assets": scene_assets})
        on_step(4, "Fetching visual assets", "shot 1/1")
        scene = SceneTrack(scene_id=1, segment="HOOK", start=0, end=2, clip_idea="city", caption="HI",
                           voiceover="hello", voice=VoiceClip(path="v.wav", duration=1.5))
        timeline = Timeline(job_id=job_id, style=GENERIC, scenes=[scene])
        return {"video_path": str(video), "timeline": timeline, "seconds": 1.0,
                "evaluation": {"scores": {"style_fidelity": 0.9}}}

    monkeypatch.setattr(agent, "generate_video", fake_generate)
    monkeypatch.setattr(agent, "load_profile", lambda: {})
    c = TestClient(server.app)
    c.calls = calls
    return c


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


# ── Creator photos: upload → match → reviewed choices reach the agent ─────────

class FakeLibrary:
    threshold = 0.064

    def __init__(self, folder):
        self.folder = folder

    def suggest(self, scenes):
        return [{"ranked": [{"name": "01_cafe.jpg", "score": 0.1}],
                 "suggested": "01_cafe.jpg" if i == 0 else None} for i, _ in enumerate(scenes)]


@pytest.fixture
def asset_client(client, monkeypatch, tmp_path):
    monkeypatch.setattr(server, "ASSET_UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(server, "_get_library",
                        lambda lib_id: FakeLibrary(server._library_dir(lib_id)))
    return client


def _upload(client):
    files = [("files", ("cafe.jpg", b"img", "image/jpeg")), ("files", ("notes.txt", b"x", "text/plain"))]
    res = client.post("/assets/upload", files=files)
    assert res.status_code == 200
    return res.json()


def test_upload_keeps_only_photos_and_serves_them(asset_client):
    data = _upload(asset_client)
    assert [p["name"] for p in data["photos"]] == ["01_cafe.jpg"]
    assert asset_client.get(data["photos"][0]["url"]).content == b"img"


def test_upload_rejects_no_photos(asset_client):
    res = asset_client.post("/assets/upload", files=[("files", ("a.txt", b"x", "text/plain"))])
    assert res.status_code == 400


def test_bad_library_ids_rejected(asset_client):
    assert asset_client.get("/assets/..%2F..%2Fserver/file/x.jpg").status_code in (400, 404)
    assert asset_client.post("/assets/match", json={"libraryId": "nope", "plan": {}}).status_code == 400
    assert asset_client.post("/assets/match", json={"libraryId": "0" * 12, "plan": {}}).status_code == 404


def test_match_returns_suggestion_per_scene(asset_client, sample_production_plan):
    lib = _upload(asset_client)["libraryId"]
    res = asset_client.post("/assets/match", json={"libraryId": lib, "plan": sample_production_plan})
    assert res.status_code == 200
    data = res.json()
    assert data["threshold"] == 0.064
    assert [s["index"] for s in data["scenes"]] == list(range(len(data["scenes"])))
    assert data["scenes"][0]["suggested"] == "01_cafe.jpg" and data["scenes"][1]["suggested"] is None


def test_reviewed_choices_reach_video_agent(asset_client, sample_production_plan):
    lib = _upload(asset_client)["libraryId"]
    res = asset_client.post("/video/generate", json={"plan": sample_production_plan, "assetLibraryId": lib,
                                                     "sceneAssets": {"0": "01_cafe.jpg", "1": None}})
    assert _wait(asset_client, res.json()["jobId"])["status"] == "done"
    call = asset_client.calls[-1]
    assert isinstance(call["assets"], FakeLibrary)
    assert call["scene_assets"] == {0: "01_cafe.jpg", 1: None}
