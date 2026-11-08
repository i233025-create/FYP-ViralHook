"""
migrate_legacy_creator.py — Give the pre-accounts creator profile to one user.

Before accounts existed, the one creator's data lived inside the repo
(module1_style_extraction/…, module2_multimodal_rag/…). This copies it into
the workspace of an existing account, so that user sees the same profile,
transcripts and style after logging in.

It COPIES (the repo layout keeps working for the CLIs and experiments) and
refuses to overwrite a workspace that already has a profile unless --force.
Stop the server first: ChromaDB is a SQLite database and should not be
copied while it is being written.

Usage (sign up in the app first, then):
  module1_style_extraction\\venv\\Scripts\\python.exe -m backend.migrate_legacy_creator --email you@example.com
"""

from __future__ import annotations

import argparse
import shutil
import sys

from sqlalchemy import select

from backend.db import get_sessionmaker, migrate
from backend.models import User
from backend.workspace import workspace_for
from pipeline.creator_paths import CreatorPaths


def copy_legacy_into(user_id: str, force: bool = False) -> list[str]:
    """Copy every legacy artifact into the user's workspace; returns what was copied."""
    legacy = CreatorPaths.legacy()
    ws = workspace_for(user_id).ensure()
    target = ws.creator
    if not legacy.text_profile.exists():
        raise SystemExit(f"No legacy profile at {legacy.text_profile} — nothing to migrate.")
    if ws.has_profile() and not force:
        raise SystemExit(f"{target.text_profile} already exists. Use --force to replace it "
                         "(the current one is archived first).")
    if ws.has_profile():
        ws.archive_profile("before-legacy-migration")

    copied = []
    for src, dst in zip(legacy.artifacts(), target.artifacts()):
        if not src.exists():
            continue
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        copied.append(f"{src.name} → {dst}")
    return copied


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", required=True, help="the account that receives the profile")
    parser.add_argument("--force", action="store_true", help="replace an existing profile (it is archived)")
    args = parser.parse_args()

    migrate()
    with get_sessionmaker()() as db:
        user = db.scalar(select(User).where(User.email == args.email.strip().lower()))
    if user is None:
        sys.exit(f"No account for {args.email}. Sign up in the app first, then run this again.")
    for line in copy_legacy_into(user.id, args.force):
        print(f"  copied {line}")
    print(f"Done: {user.email} now has the legacy creator profile.")


if __name__ == "__main__":
    main()
