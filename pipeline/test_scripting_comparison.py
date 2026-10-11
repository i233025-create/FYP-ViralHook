"""
test_scripting_comparison.py — Ablation Comparison Script
===========================================================
Runs all three scripting modes (no_history, retrieval_only, full_pipeline)
on the same topic + creator, then prints all three outputs and evaluator
scores side by side for comparison.

This is the core FYP research demonstration — showing how RAG context
and evaluator feedback progressively improve script quality.

Usage:
  python pipeline/test_scripting_comparison.py
  python pipeline/test_scripting_comparison.py "Morning Routine"

The topic defaults to whatever was last saved in test_research_output.json.
If that file doesn't exist, a hardcoded fallback topic is used.
"""

import json
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.state import PipelineState
from pipeline.agents.scripting_agent import (
    scripting_agent,
    _load_creator_profile,
    _load_chroma_retriever,
    _retrieve_examples,
    _extract_style_params,
    generate_no_history,
    generate_retrieval_only,
    generate_full_pipeline,
)
from langchain_groq import ChatGroq
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).parent.parent / "module1_style_extraction" / ".env")
load_dotenv(Path(__file__).parent.parent / ".env")

# ─── Configuration ─────────────────────────────────────────────────────────────
FALLBACK_TOPIC = "Morning Routine"
OUTPUT_FILE = Path(__file__).parent / "test_scripting_comparison_output.json"


def load_topic_from_research() -> str:
    """Load the last research agent output to get the trending topic."""
    research_path = Path(__file__).parent / "test_research_output.json"
    if research_path.exists():
        try:
            with open(research_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            topic = data.get("research_output", {}).get("topic", "")
            if topic:
                return topic
        except (json.JSONDecodeError, KeyError):
            pass
    return FALLBACK_TOPIC


def print_separator(char: str = "═", width: int = 70) -> None:
    print(char * width)


def print_script(script, mode_label: str, metadata: dict) -> None:
    """Pretty-print a single script with its metadata."""
    print_separator("─")
    print(f"  MODE: {mode_label.upper()}")
    print(f"  Concept: {script.concept_name}")
    print(f"  Hook Type: {script.hook_type}")
    print(f"  LLM Calls: {metadata.get('llm_calls', 'N/A')}")
    print(f"  Regen triggered: {metadata.get('regen_triggered', False)}")

    scores = metadata.get("evaluator_scores")
    if scores:
        print(f"\n  Evaluator Scores:")
        print(f"    Style Match:         {scores.get('style_match', 'N/A')}/10")
        print(f"    Hook Strength:       {scores.get('hook_strength', 'N/A')}/10")
        print(f"    Structure Adherence: {scores.get('structure_adherence', 'N/A')}/10")
        print(f"    Overall:             {scores.get('overall', 'N/A'):.1f}/10")
        if scores.get("feedback"):
            print(f"    Feedback: \"{scores['feedback']}\"")
    else:
        print(f"\n  Evaluator Scores: Not available for this mode")

    print(f"\n  Scenes:")
    for i, scene in enumerate(script.scenes, 1):
        print(f"\n    Scene {i} [{scene.timecode}]")
        print(f"      Visual:    {scene.clip_idea[:80]}{'...' if len(scene.clip_idea) > 80 else ''}")
        print(f"      Caption:   {scene.caption}")
        print(f"      Voiceover: {scene.voiceover[:100]}{'...' if len(scene.voiceover) > 100 else ''}")


def run_comparison(topic: str) -> dict:
    """
    Run all three modes and return comparison results.

    Runs modes sequentially with a delay between each to respect
    Groq's rate limits (30 req/min free tier).
    """
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        print("ERROR: GROQ_API_KEY not set in .env")
        sys.exit(1)

    print_separator("═")
    print("  SCRIPTING AGENT — Ablation Comparison")
    print_separator("═")
    print(f"  Topic:   {topic}")
    print(f"  Modes:   no_history | retrieval_only | full_pipeline")
    print(f"  Scenes:  5 (fixed 30-second target)")
    print_separator("═")

    # ── Load shared components ─────────────────────────────────────────────────
    print("\n[Setup] Loading creator profile and ChromaDB...")
    creator_profile = _load_creator_profile()

    if creator_profile:
        print(f"  ✓ Creator profile loaded: niche='{creator_profile.get('creator_niche', 'N/A')}'")
    else:
        print("  ⚠ Creator profile not found — run Module 1 first for best results")

    style_params = _extract_style_params(creator_profile)
    print(f"  ✓ Style params: hook='{style_params['hook_type']}', "
          f"tone='{style_params['tone']}', pacing='{style_params['pacing']}'")

    retriever = _load_chroma_retriever()
    retrieved_examples = _retrieve_examples(retriever, topic)
    if retriever:
        print(f"  ✓ RAG context retrieved ({len(retrieved_examples)} chars)")
    else:
        print("  ⚠ ChromaDB not available — retrieval modes will have limited context")

    llm = ChatGroq(
        api_key=api_key,
        model_name="openai/gpt-oss-20b",
        temperature=0.7,
        max_tokens=2048,
    )

    results = {}

    # ── Mode 1: no_history ─────────────────────────────────────────────────────
    print("\n" + "═" * 70)
    print("  RUNNING MODE 1: no_history")
    print("═" * 70)
    try:
        script_1, meta_1 = generate_no_history(topic, style_params, llm)
        results["no_history"] = {"script": script_1, "metadata": meta_1}
        print_script(script_1, "no_history", meta_1)
    except Exception as e:
        print(f"  ERROR in no_history: {e}")
        results["no_history"] = {"error": str(e)}

    print(f"\n  [Waiting 3s for rate limit...]")
    time.sleep(3)

    # ── Mode 2: retrieval_only ─────────────────────────────────────────────────
    print("\n" + "═" * 70)
    print("  RUNNING MODE 2: retrieval_only")
    print("═" * 70)
    try:
        script_2, meta_2 = generate_retrieval_only(
            topic, style_params, creator_profile, retrieved_examples, llm
        )
        results["retrieval_only"] = {"script": script_2, "metadata": meta_2}
        print_script(script_2, "retrieval_only", meta_2)
    except Exception as e:
        print(f"  ERROR in retrieval_only: {e}")
        results["retrieval_only"] = {"error": str(e)}

    print(f"\n  [Waiting 3s for rate limit...]")
    time.sleep(3)

    # ── Mode 3: full_pipeline ──────────────────────────────────────────────────
    print("\n" + "═" * 70)
    print("  RUNNING MODE 3: full_pipeline")
    print("═" * 70)
    try:
        script_3, meta_3 = generate_full_pipeline(
            topic, style_params, creator_profile, retrieved_examples, llm
        )
        results["full_pipeline"] = {"script": script_3, "metadata": meta_3}
        print_script(script_3, "full_pipeline", meta_3)
    except Exception as e:
        print(f"  ERROR in full_pipeline: {e}")
        results["full_pipeline"] = {"error": str(e)}

    # ── Summary comparison ─────────────────────────────────────────────────────
    print("\n" + "═" * 70)
    print("  COMPARISON SUMMARY")
    print("═" * 70)
    print(f"  {'Mode':<20} {'LLM Calls':<12} {'Overall Score':<15} {'Regen'}")
    print(f"  {'─'*20} {'─'*12} {'─'*15} {'─'*8}")

    for mode_key in ["no_history", "retrieval_only", "full_pipeline"]:
        r = results.get(mode_key, {})
        if "error" in r:
            print(f"  {mode_key:<20} {'ERROR':<12} {'N/A':<15} {'N/A'}")
            continue
        meta = r.get("metadata", {})
        scores = meta.get("evaluator_scores") or {}
        overall = f"{float(scores.get('overall', 0)):.1f}/10" if scores else "N/A"
        calls = str(meta.get("llm_calls", "N/A"))
        regen = "Yes" if meta.get("regen_triggered") else "No"
        print(f"  {mode_key:<20} {calls:<12} {overall:<15} {regen}")

    print("═" * 70)

    # ── Save results ───────────────────────────────────────────────────────────
    save_data = {
        "topic": topic,
        "style_params": style_params,
        "results": {
            mode: {
                "metadata": r.get("metadata", {}),
                "script": r["script"].model_dump() if "script" in r else None,
                "error": r.get("error"),
            }
            for mode, r in results.items()
        }
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False)
    print(f"\n  Full output saved to: {OUTPUT_FILE}")

    return results


if __name__ == "__main__":
    # Allow passing topic as CLI argument
    topic = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else load_topic_from_research()
    print(f"\n  Using topic: '{topic}'")
    if not sys.argv[1:]:
        print(f"  (loaded from test_research_output.json — "
              f"pass a topic as argument to override)")
    run_comparison(topic)
