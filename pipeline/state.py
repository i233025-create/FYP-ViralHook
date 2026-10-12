"""
state.py — Shared Pipeline State Schema
========================================
This file defines the single source of truth for data flowing through
the entire LangGraph pipeline. Every agent node reads from and writes
to this shared state object.

Design principles:
  - All agent output fields are Optional so the graph can be partially
    executed (e.g., run Research Agent alone for testing).
  - Each agent has a matching error field (research_error, scripting_error,
    visual_error) for consistent failure handling across all nodes.
  - Pydantic models define the typed schema for complex nested outputs
    (ScriptingOutput) so downstream nodes get validated data, not raw dicts.

Adding a new agent:
  1. Define its output as a Pydantic model below (if complex).
  2. Add <agent>_output and <agent>_error fields to PipelineState.
  3. That's it — LangGraph merges partial state updates automatically.
"""

from __future__ import annotations

from typing import Optional
from typing_extensions import TypedDict
from pydantic import BaseModel, Field


# ─── Scripting Agent Output Models ────────────────────────────────────────────
# Defined here (in state.py) so both the Scripting Agent and any downstream
# node (Visuals Agent, Streamlit UI) can import them from a single location.

class SceneOutput(BaseModel):
    """
    One scene/segment of a short-form video script.

    A 30-second reel typically has 4-6 scenes of 3-8 seconds each.
    """
    timecode: str = Field(
        description="Time range for this scene, e.g. '0:00-0:03'"
    )
    clip_idea: str = Field(
        description="Detailed visual description for B-roll or AI image generation"
    )
    caption: str = Field(
        description="Short on-screen subtitle text displayed during this scene"
    )
    voiceover: str = Field(
        description="Exact spoken narration text for this scene"
    )


class ScriptOutput(BaseModel):
    """
    One complete short-form video script with scene-by-scene breakdown.
    """
    script_id: int = Field(description="1, 2, or 3 — identifies this script variant")
    concept_name: str = Field(description="Short creative name for this script concept")
    hook_type: str = Field(
        description="Hook strategy used, e.g. 'Shock Hook', 'Mystery Hook', 'Data Hook'"
    )
    scenes: list[SceneOutput] = Field(
        description="Ordered list of scenes making up the full script"
    )


class ScriptingOutput(BaseModel):
    """
    Full output from the Scripting Agent — 3 script variants plus
    an optional final integrated script (set after human-in-the-loop step).
    """
    scripts: list[ScriptOutput] = Field(
        description="Exactly 3 distinct script variants generated for the topic"
    )
    final_script: Optional[ScriptOutput] = Field(
        default=None,
        description="Single refined script after human selects and integrates variants. "
                    "None until the integration step is triggered."
    )


# ─── Shared Pipeline State ─────────────────────────────────────────────────────
# TypedDict is used (not Pydantic BaseModel) because LangGraph requires
# TypedDict for its state schema — it performs partial dict merges internally.

class PipelineState(TypedDict):
    """
    Shared state object passed between all LangGraph nodes.

    Lifecycle:
      Entry point   → sets creator_id, creator_niche, creator_profile
      ResearchAgent → sets research_output (or research_error)
      ScriptingAgent→ sets scripting_output (or scripting_error)
      VisualsAgent  → sets visual_prompts (or visual_error)
    """

    # ── Entry point fields (set before graph execution starts) ────────────────
    creator_id: str
    # The creator's content niche, e.g. "Personal Finance", "Tech Reviews"
    # Comes from Module 1 creator_profile.json or user input at pipeline start.
    creator_niche: str

    # Full creator profile dict loaded from Module 1's creator_profile.json.
    # Accessible to ALL agents — ScriptingAgent uses tone, pacing, hooks etc.
    creator_profile: dict

    # ── Research Agent outputs ─────────────────────────────────────────────────
    # Set by research_agent.py. None until that node runs.
    research_output: Optional[dict]
    # Schema of research_output (see agents/research_agent.py):
    # {
    #   "topic": str,                      # top trend (read by ScriptingAgent)
    #   "trend_score": float,              # 0-1, measured — never LLM-made
    #   "trend_signals": {"velocity": float, "engagement_rate": float, "outlier": float},
    #   "creator_fit": float,              # cosine vs recurring_topics
    #   "why_trending": str, "suggested_angle": str,
    #   "niche": str,
    #   "supporting_evidence": [
    #       {"video_title": str, "channel": str, "views": int,
    #        "published_hours_ago": float, "url": str}
    #   ],
    #   "related_keywords": [str],         # search queries used
    #   "cluster_size": int, "low_confidence": bool,
    #   "source": "youtube_data_api" | "profile_fallback",
    #   "trends": [ ...all ranked trends with full evidence... ]
    # }
    research_error: Optional[str]

    # ── Scripting Agent outputs ────────────────────────────────────────────────
    # Set by scripting_agent.py (Module 2). None until that node runs.
    scripting_output: Optional[ScriptingOutput]
    scripting_error: Optional[str]

    # ── Visuals Agent outputs ──────────────────────────────────────────────────
    # Set by visuals_agent.py (Module 3). None until that node runs.
    visual_prompts: Optional[list]
    visual_error: Optional[str]
