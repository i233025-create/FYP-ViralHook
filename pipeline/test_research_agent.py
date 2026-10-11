"""
test_research_agent.py — Standalone test for the Research Agent node.

Run with:
  python test_research_agent.py

Tests the node in isolation without spinning up the full LangGraph pipeline.
Prints the resulting research_output to console and saves it to a JSON file.

Change TEST_NICHE below to test different niches.
"""

import json
import sys
from pathlib import Path

# Add project root to path so pipeline imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.state import PipelineState
from pipeline.agents.research_agent import research_agent

# ─── Test Configuration ────────────────────────────────────────────────────────
TEST_NICHE = "Personal Growth"   # Change this to test different niches
TEST_CREATOR_ID = "test_creator_001"


def run_test():
    print("=" * 60)
    print("  Research Agent — Standalone Test")
    print("=" * 60)
    print(f"  Niche:      {TEST_NICHE}")
    print(f"  Creator ID: {TEST_CREATOR_ID}")
    print("=" * 60)

    # Build a minimal PipelineState — only fields the research agent reads
    test_state: PipelineState = {
        "creator_id": TEST_CREATOR_ID,
        "creator_niche": TEST_NICHE,
        "creator_profile": {},   # Empty for this test — research agent doesn't use it
        "research_output": None,
        "research_error": None,
        "scripting_output": None,
        "scripting_error": None,
        "visual_prompts": None,
        "visual_error": None,
    }

    # Run the node directly
    result = research_agent(test_state)

    print("\n" + "=" * 60)
    print("  Result")
    print("=" * 60)

    if result.get("research_error"):
        print(f"\n  ⚠ Error/Warning: {result['research_error']}")
        if result.get("research_output", {}).get("fallback"):
            print("  ℹ Fallback topic was used (Google Trends unavailable)")

    if result.get("research_output"):
        output = result["research_output"]
        print(f"\n  ✓ Topic:       {output['topic']}")
        print(f"  ✓ Niche:       {output['niche']}")
        print(f"  ✓ Trend Score: {output['trend_score']}")
        print(f"  ✓ Cluster Size:{output.get('cluster_size', 'N/A')}")
        print(f"  ✓ Confidence:  {'⚠ LOW (single-video cluster)' if output.get('low_confidence') else '✓ OK (multi-video cluster)'}")
        print(f"  ✓ Velocity:    {output['trend_signals']['velocity']}")
        print(f"  ✓ Engagement:  {output['trend_signals']['engagement_rate']}")
        print(f"\n  Related Keywords:")
        for kw in output.get("related_keywords", []):
            print(f"    - {kw}")
        print(f"\n  Supporting Evidence (top trending videos):")
        for ev in output.get("supporting_evidence", []):
            print(f"    - \"{ev.get('video_title', ev.get('keyword', 'N/A'))}\"")
            print(f"      Channel: {ev.get('channel', 'N/A')} | "
                  f"Views: {ev.get('views', ev.get('peak_interest', 'N/A'))} | "
                  f"Published: {ev.get('published_hours_ago', 'N/A')}h ago")

        # Save full output to file for inspection
        output_path = Path(__file__).parent / "test_research_output.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\n  Full output saved to: {output_path}")
    else:
        print("\n  ✗ No research_output returned")

    print("\n" + "=" * 60)
    return result


if __name__ == "__main__":
    # Allow overriding niche from command line: python test_research_agent.py "Tech Reviews"
    if len(sys.argv) > 1:
        TEST_NICHE = " ".join(sys.argv[1:])
    run_test()
