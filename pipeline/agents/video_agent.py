"""
video_agent.py — Module 4: Video Generation Agent
==================================================
Script (Scripting Agent output or frontend production plan) + creator profile
→ rendered 1080×1920 MP4, timeline.json and a measured evaluation.

  1. style plan     profile → StyleParams        (pipeline/video/style_plan.py)
  2. voiceover      Kokoro per scene, wpm-calibrated → real scene timing
  3. shot plan      scene ÷ shot_duration → sub-shots + search queries
  4. assets         Pexels+CLIP → SDXL-Lightning → placeholder, per shot
  5. timeline       timeline.json (single source of truth)
  6. render         FFmpeg + burned-in captions
  7. evaluate       Module 2 extractors on the MP4 vs the creator profile

Modes:
  personalised — edit parameters measured from the creator's own videos
  generic      — fixed template defaults (the baseline)

Output: pipeline/output/video/<job_id>/{final.mp4, timeline.json, evaluation.json}

CLI:
  python -m pipeline.agents.video_agent                       # personalised
  python -m pipeline.agents.video_agent --compare             # both modes + deltas
  python -m pipeline.agents.video_agent --script my.json --script-mode full_pipeline
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Callable

# Kokoro, CLIP and SDXL share one 10 GB GPU; must be set before CUDA initialises
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.video import renderer                                   # noqa: E402
from pipeline.video.assets import AssetResolver                       # noqa: E402
from pipeline.video.evaluator import compare, evaluate                # noqa: E402
from pipeline.video.shot_planner import image_prompt, plan_queries    # noqa: E402
from pipeline.video.style_plan import plan_style                      # noqa: E402
from pipeline.video.timeline import (                                 # noqa: E402
    SceneTrack, Shot, Timeline, dump_json, layout_scenes, motion_for, normalize_scenes, split_shots,
)
from pipeline.video.tts import KokoroTTS, TTSEngine, synthesize_scene  # noqa: E402

OUTPUT_DIR = ROOT / "pipeline" / "output" / "video"
CACHE_DIR = ROOT / "pipeline" / "cache" / "video_assets"
MULTIMODAL_PROFILE = ROOT / "module2_multimodal_rag" / "creator_profile_multimodal.json"
TEXT_PROFILE = ROOT / "module1_style_extraction" / "creator_profile.json"
DEFAULT_SCRIPT = ROOT / "pipeline" / "test_scripting_comparison_output.json"

STEPS = [
    "Planning edit style",
    "Generating voiceover",
    "Planning shots",
    "Fetching visual assets",
    "Building timeline",
    "Rendering video",
    "Evaluating video",
]

StepCallback = Callable[[int, str, str], None]   # (step 1-7, label, detail)


def load_profile() -> dict:
    """Multimodal profile (has measured visual/audio stats) over the text-only one."""
    profile = {}
    for path in (TEXT_PROFILE, MULTIMODAL_PROFILE):
        if path.exists():
            profile.update(json.loads(path.read_text(encoding="utf-8")))
    return profile


def generate_video(script, profile: dict, mode: str = "personalised",
                   job_id: str | None = None, out_dir: str | Path | None = None,
                   on_step: StepCallback | None = None,
                   tts: TTSEngine | None = None, resolver: AssetResolver | None = None,
                   use_llm: bool = True, run_evaluation: bool = True, title: str = "ViralHook") -> dict:
    """
    Run the full pipeline once. Returns
      {job_id, mode, video_path, timeline_path, timeline, evaluation, seconds}
    """
    started = time.time()
    job_id = job_id or uuid.uuid4().hex[:12]
    job_dir = Path(out_dir or OUTPUT_DIR / job_id)
    work = job_dir / "work"
    work.mkdir(parents=True, exist_ok=True)

    def step(n: int, detail: str = ""):
        print(f"[VideoAgent] {n}/{len(STEPS)} {STEPS[n - 1]} {detail}".rstrip())
        if on_step:
            on_step(n, STEPS[n - 1], detail)

    scenes = normalize_scenes(script)

    # 1. Style
    step(1, mode)
    style = plan_style(profile, mode)

    # 2. Voiceover → real timing
    tts = tts or KokoroTTS()
    voices = []
    for i, sc in enumerate(scenes):
        step(2, f"scene {i + 1}/{len(scenes)}")
        voices.append(synthesize_scene(tts, sc["voiceover"], str(work / f"vo_{i + 1:02d}.wav"),
                                       style.target_wpm))
    windows = layout_scenes([v.duration for v in voices], style.scene_gap)

    # 3. Shots
    tracks, shot_index = [], 0
    niche = profile.get("creator_niche", "")
    for i, (sc, voice, (start, end)) in enumerate(zip(scenes, voices, windows)):
        step(3, f"scene {i + 1}/{len(scenes)}")
        bounds = split_shots(start, end, style.shot_duration)
        queries, _ = plan_queries(sc["clip_idea"], sc["voiceover"], len(bounds), niche, use_llm=use_llm)
        shots = []
        for (s, e), q in zip(bounds, queries):
            shots.append(Shot(start=s, end=e, query=q, image_prompt=image_prompt(q, sc["clip_idea"]),
                              motion=motion_for(shot_index)))
            shot_index += 1
        tracks.append(SceneTrack(scene_id=i + 1, segment=sc["segment"], start=start, end=end,
                                 clip_idea=sc["clip_idea"], caption=sc["caption"],
                                 voiceover=sc["voiceover"], voice=voice, shots=shots))

    # 4. Assets
    resolver = resolver or AssetResolver(CACHE_DIR)
    used_ids: set = set()
    total = sum(len(t.shots) for t in tracks)
    done = 0
    for track in tracks:
        for shot in track.shots:
            done += 1
            step(4, f"shot {done}/{total}: {shot.query}")
            shot.asset = resolver.resolve(shot.query, shot.image_prompt, used_ids)
    resolver.release()

    # 5. Timeline
    step(5)
    timeline = Timeline(job_id=job_id, title=title, style=style, scenes=tracks)
    timeline_path = timeline.save(job_dir / "timeline.json")

    # 6. Render
    step(6)
    video_path = renderer.render(timeline, job_dir / "final.mp4", work,
                                 on_progress=lambda k, n: step(6, f"shot {k}/{n}") if k == n or k % 5 == 0 else None)

    # 7. Evaluate
    evaluation = None
    if run_evaluation:
        step(7)
        try:
            evaluation = evaluate(video_path, timeline, profile, work, clean_video=work / "video.mp4",
                                  scorer=getattr(resolver, "scorer", None))
            dump_json(evaluation, job_dir / "evaluation.json")
        except Exception as e:   # evaluation must never lose a finished render
            print(f"[VideoAgent] Evaluation failed: {e}")
            evaluation = {"error": str(e)}

    return {
        "job_id": job_id,
        "mode": mode,
        "video_path": str(video_path),
        "timeline_path": str(timeline_path),
        "timeline": timeline,
        "evaluation": evaluation,
        "seconds": round(time.time() - started, 1),
    }


def compare_modes(script, profile: dict, out_dir: str | Path | None = None, **kwargs) -> dict:
    """Render personalised and generic from the same script; assets are shared via the cache."""
    base = Path(out_dir or OUTPUT_DIR / f"compare_{uuid.uuid4().hex[:8]}")
    resolver = kwargs.pop("resolver", None) or AssetResolver(CACHE_DIR)
    tts = kwargs.pop("tts", None) or KokoroTTS()
    results = {mode: generate_video(script, profile, mode=mode, out_dir=base / mode,
                                    resolver=resolver, tts=tts, **kwargs)
               for mode in ("personalised", "generic")}
    report = {mode: {"video_path": r["video_path"], "evaluation": r["evaluation"]}
              for mode, r in results.items()}
    p_eval, g_eval = results["personalised"]["evaluation"], results["generic"]["evaluation"]
    if p_eval and g_eval and "scores" in p_eval and "scores" in g_eval:
        report["comparison"] = compare(p_eval, g_eval)
    dump_json(report, base / "comparison.json")
    return report


def _load_script(path: Path, script_mode: str):
    """Accept a scripting comparison output, a bare ScriptOutput, or a production plan."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if "results" in data:
        return data["results"][script_mode]["script"], data.get("topic", "ViralHook")
    return data, data.get("title") or data.get("concept_name") or "ViralHook"


def main():
    from dotenv import load_dotenv

    load_dotenv(ROOT / "module1_style_extraction" / ".env")
    load_dotenv(ROOT / ".env")

    parser = argparse.ArgumentParser(description="ViralHook video generation (Module 4)")
    parser.add_argument("--script", type=Path, default=DEFAULT_SCRIPT)
    parser.add_argument("--script-mode", default="full_pipeline",
                        help="Which result to use from a scripting comparison file")
    parser.add_argument("--mode", choices=["personalised", "generic"], default="personalised")
    parser.add_argument("--compare", action="store_true", help="Render both modes and compare")
    parser.add_argument("--no-llm", action="store_true", help="Keyword shot queries, no Ollama")
    args = parser.parse_args()

    script, title = _load_script(args.script, args.script_mode)
    profile = load_profile()
    if args.compare:
        report = compare_modes(script, profile, use_llm=not args.no_llm, title=title)
        print(json.dumps(report.get("comparison", report), indent=2))
    else:
        result = generate_video(script, profile, mode=args.mode, use_llm=not args.no_llm, title=title)
        print(f"\nVideo     : {result['video_path']}\nTimeline  : {result['timeline_path']}"
              f"\nTook      : {result['seconds']}s")
        print(json.dumps(result["evaluation"], indent=2))


if __name__ == "__main__":
    main()
