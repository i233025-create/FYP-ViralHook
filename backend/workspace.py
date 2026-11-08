"""
workspace.py — One folder per user for everything the AI pipeline produces.

  data/users/<user_id>/
    input_videos/  chroma_db/  creator_profile.json          (Module 1)
    creator_profile_multimodal.json  qdrant_snapshot.json    (Module 2)
    assets/<library_id>/      the creator's uploaded photos (E3)
    videos/<job_id>/          rendered videos
    archive/<stamp>/          the previous profile, kept when onboarding re-runs

No path in a request ever reaches the filesystem unchecked: user ids come
from the session, library/job ids must be 12 hex characters, and file names
are reduced to their base name.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from fastapi import Depends

from backend.auth import get_current_user
from backend.config import DATA_DIR
from backend.models import User
from pipeline.creator_paths import WORKSPACE_ENV, CreatorPaths

USERS_DIR = DATA_DIR / "users"
_ID = re.compile(r"[0-9a-f]{12,32}")


@dataclass(frozen=True)
class Workspace:
    root: Path

    @property
    def creator(self) -> CreatorPaths:
        return CreatorPaths.at(self.root)

    @property
    def assets_dir(self) -> Path:
        return self.root / "assets"

    @property
    def videos_dir(self) -> Path:
        return self.root / "videos"

    @property
    def archive_dir(self) -> Path:
        return self.root / "archive"

    def ensure(self) -> "Workspace":
        self.root.mkdir(parents=True, exist_ok=True)
        return self

    def has_profile(self) -> bool:
        return self.creator.text_profile.exists()

    def subprocess_env(self) -> dict[str, str]:
        """Environment for Module 1 / 2 subprocesses so they write here."""
        return {WORKSPACE_ENV: str(self.root)}

    # ── Re-running onboarding replaces the creator's profile ─────────────────

    def archive_profile(self, stamp: str) -> Path:
        """Move the current profile artifacts to archive/<stamp>/ (restorable)."""
        dest = self.archive_dir / stamp
        for src in self.creator.artifacts():
            if src.exists():
                dest.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dest / src.name))
        return dest

    def restore_profile(self, archive: Path) -> None:
        """Undo a failed extraction: park its partial output, bring the old profile back."""
        failed = archive.with_name(archive.name + "_failed")
        for cur in self.creator.artifacts():
            old = archive / cur.name
            if cur.exists():
                failed.mkdir(parents=True, exist_ok=True)
                shutil.move(str(cur), str(failed / cur.name))
            if old.exists():
                shutil.move(str(old), str(cur))


def workspace_for(user_id: str) -> Workspace:
    if not _ID.fullmatch(user_id or ""):
        raise ValueError(f"Bad user id: {user_id!r}")
    return Workspace(USERS_DIR / user_id)


def current_workspace(user: User = Depends(get_current_user)) -> Workspace:
    """FastAPI dependency: the signed-in user's workspace (created on first use)."""
    return workspace_for(user.id).ensure()


def child_dir(parent: Path, item_id: str) -> Path | None:
    """parent/<item_id> for a 12-hex id that exists, else None (never escapes parent)."""
    if not re.fullmatch(r"[0-9a-f]{12}", item_id or ""):
        return None
    path = parent / item_id
    return path if path.is_dir() else None


__all__ = ["Workspace", "workspace_for", "current_workspace", "child_dir", "USERS_DIR"]
