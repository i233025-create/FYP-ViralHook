"""Per-user workspaces: paths, archive/restore, id safety, and per-user profiles."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from backend.workspace import Workspace, child_dir, workspace_for
from pipeline.creator_paths import WORKSPACE_ENV, CreatorPaths

ROOT = Path(__file__).parent.parent.parent


def test_creator_paths_layouts(tmp_path, monkeypatch):
    ws = CreatorPaths.at(tmp_path)
    assert ws.text_profile == tmp_path / "creator_profile.json"
    assert ws.chroma_db == tmp_path / "chroma_db"
    legacy = CreatorPaths.legacy()
    assert legacy.text_profile.parent.name == "module1_style_extraction"
    assert legacy.qdrant_snapshot.parent.name == "module2_multimodal_rag"
    monkeypatch.setenv(WORKSPACE_ENV, str(tmp_path))
    assert CreatorPaths.from_env() == ws
    monkeypatch.delenv(WORKSPACE_ENV)
    assert CreatorPaths.from_env() == legacy


def test_workspace_for_rejects_path_tricks():
    for bad in ["", "../etc", "abc", "0123456789ab/..", "A" * 32]:
        with pytest.raises(ValueError):
            workspace_for(bad)
    assert workspace_for("0" * 32).root.name == "0" * 32


def test_child_dir_never_escapes(tmp_path):
    (tmp_path / "0123456789ab").mkdir()
    assert child_dir(tmp_path, "0123456789ab") == tmp_path / "0123456789ab"
    assert child_dir(tmp_path, "..") is None
    assert child_dir(tmp_path, "ffffffffffff") is None   # well-formed but missing


def test_archive_and_restore_round_trip(tmp_path):
    ws = Workspace(tmp_path)
    paths = ws.creator
    paths.input_videos.mkdir(parents=True)
    (paths.input_videos / "a.mp4").write_bytes(b"v")
    paths.text_profile.write_text('{"old": true}')

    archive = ws.archive_profile("20261108-120000")
    assert not paths.text_profile.exists() and not paths.input_videos.exists()

    paths.text_profile.write_text('{"partial": true}')   # a failed new extraction
    ws.restore_profile(archive)
    assert json.loads(paths.text_profile.read_text()) == {"old": True}
    assert (paths.input_videos / "a.mp4").exists()
    assert (archive.with_name(archive.name + "_failed") / "creator_profile.json").exists()


def test_module1_config_follows_the_workspace(tmp_path):
    """The server hands the workspace to Module 1 via the environment."""
    code = ("import sys; sys.path.insert(0, 'module1_style_extraction'); import config as c; "
            "print(c.CHROMA_PERSIST_DIR); print(c.OUTPUT_FILE); print(c.LOCAL_VIDEO_DIR)")
    env = {**os.environ, WORKSPACE_ENV: str(tmp_path)}
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True,
                         text=True, check=True).stdout.split()
    expected = [tmp_path / "chroma_db", tmp_path / "creator_profile.json", tmp_path / "input_videos"]
    assert [Path(p) for p in out] == expected


def test_profile_endpoint_is_per_user(make_user_client):
    pytest.importorskip("httpx")
    from backend.workspace import workspace_for as ws_for

    alice, bob = make_user_client("alice@example.com"), make_user_client("bob@example.com")
    assert alice.get("/onboarding/profile").status_code == 404   # nobody has a profile yet

    ws = ws_for(alice.user_id).ensure()
    ws.creator.text_profile.write_text(json.dumps({"creator_niche": "Food", "summary": "Alice's style"}),
                                       encoding="utf-8")
    assert alice.get("/onboarding/profile").status_code == 200
    assert bob.get("/onboarding/profile").status_code == 404     # Alice's profile is not Bob's


def test_legacy_migration_copies_and_refuses_to_overwrite(tmp_path, monkeypatch):
    import backend.migrate_legacy_creator as mig
    from backend import workspace

    legacy_root = tmp_path / "legacy"
    legacy = CreatorPaths.at(legacy_root)
    legacy.chroma_db.mkdir(parents=True)
    (legacy.chroma_db / "chroma.sqlite3").write_bytes(b"db")
    legacy.text_profile.write_text('{"creator_niche": "Tech"}')
    monkeypatch.setattr(mig.CreatorPaths, "legacy", classmethod(lambda cls: legacy))
    monkeypatch.setattr(workspace, "USERS_DIR", tmp_path / "users")

    uid = "a" * 32
    copied = mig.copy_legacy_into(uid)
    target = workspace.workspace_for(uid).creator
    assert len(copied) == 2 and target.text_profile.exists() and (target.chroma_db / "chroma.sqlite3").exists()
    assert legacy.text_profile.exists()          # copied, not moved
    with pytest.raises(SystemExit):
        mig.copy_legacy_into(uid)                # already has a profile
    mig.copy_legacy_into(uid, force=True)        # archived, then replaced
    assert (workspace.workspace_for(uid).archive_dir / "before-legacy-migration" / "creator_profile.json").exists()
