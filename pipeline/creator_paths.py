"""
creator_paths.py — Where one creator's data lives.

Every artifact that belongs to a single creator (uploaded videos, Module 1's
ChromaDB and profile, Module 2's profile and Qdrant snapshot) is addressed
through a CreatorPaths object, so the product can keep one folder per user.

  CreatorPaths.legacy()   the original single-creator layout inside the repo
                          (module1_style_extraction/…, module2_multimodal_rag/…),
                          used by the CLIs, experiments and tests by default
  CreatorPaths.at(root)   everything under one folder (a user's workspace)
  CreatorPaths.from_env() at($VIRALHOOK_WORKSPACE) if set, else legacy() —
                          how the server hands a workspace to the Module 1 / 2
                          subprocesses
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).parent.parent.resolve()
WORKSPACE_ENV = "VIRALHOOK_WORKSPACE"


@dataclass(frozen=True)
class CreatorPaths:
    input_videos: Path
    chroma_db: Path
    temp_audio: Path
    text_profile: Path          # Module 1 creator_profile.json
    multimodal_profile: Path    # Module 2 creator_profile_multimodal.json
    qdrant_snapshot: Path       # Module 2 qdrant_snapshot.json

    @classmethod
    def legacy(cls) -> "CreatorPaths":
        m1, m2 = ROOT / "module1_style_extraction", ROOT / "module2_multimodal_rag"
        return cls(input_videos=m1 / "input_videos", chroma_db=m1 / "chroma_db", temp_audio=m1 / "temp_audio",
                   text_profile=m1 / "creator_profile.json",
                   multimodal_profile=m2 / "creator_profile_multimodal.json",
                   qdrant_snapshot=m2 / "qdrant_snapshot.json")

    @classmethod
    def at(cls, root: str | Path) -> "CreatorPaths":
        root = Path(root)
        return cls(input_videos=root / "input_videos", chroma_db=root / "chroma_db", temp_audio=root / "temp_audio",
                   text_profile=root / "creator_profile.json",
                   multimodal_profile=root / "creator_profile_multimodal.json",
                   qdrant_snapshot=root / "qdrant_snapshot.json")

    @classmethod
    def from_env(cls) -> "CreatorPaths":
        root = os.getenv(WORKSPACE_ENV, "").strip()
        return cls.at(root) if root else cls.legacy()

    def artifacts(self) -> list[Path]:
        """Everything that is replaced when the creator re-runs onboarding."""
        return [self.input_videos, self.chroma_db, self.text_profile,
                self.multimodal_profile, self.qdrant_snapshot]
