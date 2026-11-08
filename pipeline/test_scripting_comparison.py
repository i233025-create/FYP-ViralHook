"""
test_scripting_comparison.py — Ablation study for the Scripting Agent.

Run with:
  python pipeline/test_scripting_comparison.py
  python pipeline/test_scripting_comparison.py "Stop comparing yourself"   # custom topic

Runs the SAME topic and hook type through all three modes and scores every
script with the SAME evaluator, so the table is a fair comparison:

  no_history      topic + trend context only (baseline)
  retrieval_only  + creator profile, word budget, real transcripts
  full_pipeline   + evaluate → rewrite-with-feedback loop

The topic and trend context default to the last Research Agent run
(pipeline/test_research_output.json). Results are saved to
pipeline/test_scripting_comparison_output.json.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.agents.scripting_agent import MODES, run_ablation  # noqa: E402

FALLBACK_TOPIC = "Stop comparing yourself to others"
RESEARCH_OUTPUT = Path(__file__).parent / "test_research_output.json"
OUTPUT_FILE = Path(__file__).parent / "test_scripting_comparison_output.json"
METRICS = ("style_match", "timing", "structure", "hook_strength", "overall")


def load_trend() -> dict | None:
    """Top trend from the last research run, if there is one."""
    if not RESEARCH_OUTPUT.exists():
        return None
    try:
        output = json.loads(RESEARCH_OUTPUT.read_text(encoding="utf-8"))["research_output"]
    except (ValueError, KeyError):
        return None
    trends = output.get("trends") or []
    return trends[0] if trends else ({"topic": output["topic"]} if output.get("topic") else None)


def _fmt(value) -> str:
    return "  n/a" if value is None else f"{value:5.1f}"


def main(topic_arg: str | None = None):
    trend = None if topic_arg else load_trend()
    topic = topic_arg or (trend or {}).get("topic") or FALLBACK_TOPIC

    print("=" * 72)
    print("  Scripting Agent — Ablation (same topic, same hook, same evaluator)")
    print("=" * 72)
    print(f"  Topic: {topic}")
    print(f"  Trend context: {'yes' if trend else 'no'}")

    started = time.time()
    results = run_ablation(topic, trend=trend)
    elapsed = time.time() - started

    print("\n" + "=" * 72)
    print(f"  {'mode':<16}" + "".join(f"{m:>15}" for m in METRICS) + "   attempts")
    print("  " + "-" * 92)
    for mode in MODES:
        _, meta = results[mode]
        scores = meta["evaluator_scores"]
        print(f"  {mode:<16}" + "".join(f"{_fmt(scores[m]):>15}" for m in METRICS)
              + f"   {len(meta['all_scores'])}")

    baseline = results[MODES[0]][1]["baseline"]
    print(f"\n  Style baseline: {baseline['transcripts']} transcripts "
          f"({baseline.get('transcripts_excluded', 0)} excluded), {baseline.get('baseline_words', 0)} words, "
          f"{baseline['wpm']} wpm ({baseline['wpm_source']}), budget {baseline['word_budget']} words")
    if not baseline["measured_style"]:
        print("  ⚠ style_match is n/a: no usable English transcripts in ChromaDB — re-run Module 1.")
    elif baseline.get("low_confidence"):
        print("  ⚠ style baseline is LOW CONFIDENCE (< 150 words of the creator's speech). Add more "
              "English Shorts to module1_style_extraction/input_videos and re-run Module 1.")
    print(f"  Total time: {elapsed:.0f} s")

    for mode in MODES:
        script, meta = results[mode]
        print(f"\n  ── {mode} ── {script.concept_name}")
        for scene in script.scenes:
            print(f"     {scene.timecode:<10} {scene.voiceover}")
        if meta["evaluator_scores"]["feedback"]:
            print("     Remaining issues: " + " | ".join(meta["evaluator_scores"]["feedback"]))

    OUTPUT_FILE.write_text(json.dumps({
        "topic": topic,
        "trend": trend,
        "elapsed_s": round(elapsed, 1),
        "results": {mode: {"script": s.model_dump(), "metadata": m} for mode, (s, m) in results.items()},
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Full output saved to: {OUTPUT_FILE}")
    print("=" * 72)


if __name__ == "__main__":
    main(" ".join(sys.argv[1:]) or None)
