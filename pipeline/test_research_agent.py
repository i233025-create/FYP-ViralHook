"""
test_research_agent.py — Standalone live test for the Research Agent node.

Run with:
  python pipeline/test_research_agent.py
  python pipeline/test_research_agent.py "Tech Reviews"    # override niche

Uses the real creator_profile.json from Module 1, the real YouTube Data API
(YOUTUBE_API_KEY) and the local LLM if Ollama is running. Prints every trend
with its evidence and saves the full output to test_research_output.json.
"""

import json
import sys
from pathlib import Path

# Add project root to path so pipeline imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.state import PipelineState  # noqa: E402
from pipeline.agents.research_agent import research_agent  # noqa: E402

# ─── Test Configuration ────────────────────────────────────────────────────────
PROFILE_PATH = Path(__file__).parent.parent / "module1_style_extraction" / "creator_profile.json"
TEST_CREATOR_ID = "test_creator_001"


def run_test(niche: str | None = None):
    profile = {}
    if PROFILE_PATH.exists():
        profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    niche = niche or profile.get("creator_niche", "Personal Growth")

    print("=" * 60)
    print("  Research Agent — Standalone Test")
    print("=" * 60)
    print(f"  Niche:   {niche}")
    print(f"  Profile: {'loaded' if profile else 'NOT FOUND — fallback queries only'}")
    print("=" * 60)

    test_state: PipelineState = {
        "creator_id": TEST_CREATOR_ID,
        "creator_niche": niche,
        "creator_profile": profile,
        "research_output": None,
        "research_error": None,
        "scripting_output": None,
        "scripting_error": None,
        "visual_prompts": None,
        "visual_error": None,
    }

    result = research_agent(test_state)
    output = result["research_output"]

    print("\n" + "=" * 60)
    if result.get("research_error"):
        print(f"  ⚠ Error: {result['research_error']}")
    print(f"  Source:  {output['source']}")
    print(f"  Queries: {output['related_keywords']}")

    for i, trend in enumerate(output.get("trends", []), 1):
        print(f"\n  #{i} {trend['topic']}"
              f"{'   ⚠ low confidence' if trend['low_confidence'] else ''}")
        print(f"     trend={trend['trend_score']:.2f}  fit={trend['creator_fit']:.2f}  "
              f"videos={trend['video_count']}  channels={trend['channel_count']}  "
              f"label={trend['labeled_by']}")
        print(f"     {trend['data_summary']}")
        if trend["why_trending"]:
            print(f"     Why:   {trend['why_trending']}")
        if trend["suggested_angle"]:
            print(f"     Angle: {trend['suggested_angle']}")
        for e in trend["evidence"]:
            reuploads = f" | +{e['reuploads']} reuploads" if e.get("reuploads") else ""
            print(f"       - {e['title'][:60]} | {e['channel']} | {e['views']:,} views "
                  f"| {e['outlier']:.1f}× subs{reuploads} | {e['url']}")

    if not output.get("trends"):
        print(f"\n  Fallback topic: {output['topic']}")

    output_path = Path(__file__).parent / "test_research_output.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n  Full output saved to: {output_path}")
    print("=" * 60)
    return result


if __name__ == "__main__":
    run_test(" ".join(sys.argv[1:]) or None)
