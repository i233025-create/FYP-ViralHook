"""
server.py — ViralHook PoC Backend
===================================
Endpoints:

  GET  /health
  GET  /onboarding/profile        → reads creator_profile.json → frontend profile shape
  POST /research/trends           → Research Agent: trending topics from real YouTube Shorts
  POST /script/generate           → Scripting Agent: 3 hook variants, measured evaluator
  POST /export/xml                → Premiere Pro XML from production plan
  POST /video/generate            → Video Agent: start a render job (returns job_id)
  GET  /video/status/{job_id}     → job progress, timeline + evaluation when done
  GET  /video/file/{job_id}       → the rendered MP4

Run:
  module1_style_extraction\\venv\\Scripts\\python.exe -m uvicorn server:app --reload --port 8000
"""

import os
import sys
import json
import re
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# ── Paths & env ───────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / "module1_style_extraction" / ".env")
load_dotenv(ROOT / ".env")

PROFILE_PATH = ROOT / "module1_style_extraction" / "creator_profile.json"
MULTIMODAL_PROFILE_PATH = ROOT / "module2_multimodal_rag" / "creator_profile_multimodal.json"

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="ViralHook PoC API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _parse_timecode(tc: str):
    m = re.match(r"(\d+):(\d+)\s*[-–]\s*(\d+):(\d+)", tc.strip())
    if not m:
        return "00:00", "00:05"
    sm, ss, em, es = m.groups()
    return f"{int(sm):02d}:{int(ss):02d}", f"{int(em):02d}:{int(es):02d}"


def _scene_to_frontend(scene, index: int, total: int) -> dict:
    s = scene if isinstance(scene, dict) else scene.model_dump()
    start, end = _parse_timecode(s.get("timecode", f"0:0{index*5}-0:0{(index+1)*5}"))
    _segments = ["HOOK", "SETUP", "MAIN POINT", "EVIDENCE", "CONCLUSION"]
    segment = _segments[min(index, len(_segments) - 1)] if total <= 5 else _segments[int((index / max(total - 1, 1)) * 4)]
    clip = s.get("clip_idea", "")
    if "talking" in clip.lower() or "face" in clip.lower():
        shot = "Close-up talking head"
    elif "screen" in clip.lower() or "code" in clip.lower():
        shot = "Screen recording"
    else:
        shot = "Medium shot"
    return {
        "id": f"s{index+1}",
        "startTime": start,
        "endTime": end,
        "segment": segment,
        "voiceover": s.get("voiceover", ""),
        "caption": s.get("caption", ""),
        "shot": shot,
        "visual": clip,
    }


def _score_pct(scores: dict, key: str) -> Optional[int]:
    """Evaluator 0-10 → 0-100. None stays None (metric could not be measured)."""
    value = scores.get(key)
    if value is None:
        return None
    return max(0, min(100, round(float(value) * 10)))


def _script_to_variant(script, metadata: dict, topic: str, index: int) -> dict:
    """Map a scripting_agent result to the variant card the frontend renders."""
    s = script if isinstance(script, dict) else script.model_dump()
    scenes_raw = s.get("scenes", [])
    scenes = [_scene_to_frontend(sc, i, len(scenes_raw)) for i, sc in enumerate(scenes_raw)]
    scores = metadata.get("evaluator_scores") or {}
    return {
        "id": f"sv_{index + 1}",
        "label": f"VARIANT {chr(ord('A') + index)}",
        "topic": topic,
        "hook": scenes[0]["voiceover"] if scenes else "",
        "hookType": s.get("hook_type", "Bold Claim"),
        "structure": metadata.get("structure", ""),
        # All measured by the evaluator; None = not measurable (e.g. no transcripts yet)
        "styleConsistency":   _score_pct(scores, "style_match"),
        "hookAlignment":      _score_pct(scores, "hook_strength"),
        "structureAlignment": _score_pct(scores, "structure"),
        "timingFit":          _score_pct(scores, "timing"),
        "overall":            _score_pct(scores, "overall"),
        "scenes": scenes,
        "mode": metadata.get("mode", "full_pipeline"),
        "regenTriggered": metadata.get("regen_triggered", False),
        "evaluatorScores": scores,
        "feedback": scores.get("feedback", []),
    }


def _raw_profile_to_frontend(raw: dict, handle: str = "", niche: str = "") -> dict:
    """
    Translate creator_profile.json (Module 1 output) → frontend CreatorProfile shape.
    Matches the shape used by DashboardScreen and ExperiencedCreatorScreen.
    """
    hooks = raw.get("signature_hooks", [])
    dominant_hook = hooks[0] if hooks else "Contrarian"

    structure = raw.get("typical_structure", "Hook → Problem → Solution")

    style_summary = raw.get("content_style_summary", "")
    if not style_summary:
        tone   = raw.get("dominant_tone", "")
        pacing = raw.get("avg_pacing", "")
        style_summary = f"{tone} tone, {pacing} pacing. Extracted from transcript analysis."

    resolved_niche  = niche  or raw.get("creator_niche", "Tech")
    resolved_handle = handle or "@creator"
    if not resolved_handle.startswith("@"):
        resolved_handle = "@" + resolved_handle

    name = resolved_handle.lstrip("@").replace("_", " ").title()

    return {
        "id": "cp_real",
        "type": "experienced",
        "name": name,
        "handle": resolved_handle,
        "niche": resolved_niche,
        "dominantHookType": dominant_hook,
        "dominantStructure": structure,
        "styleSummary": style_summary,
        "analyzedVideos": raw.get("_analyzed_videos", 3),   # stored by pipeline if available
        "drafts": 0,
        "scheduled": 0,
        "published": 0,
        "pocNote": True,
        # Pass raw profile through so frontend can show extra detail if needed
        "rawProfile": raw,
    }


# ══════════════════════════════════════════════════════════════════════════════
# REQUEST SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class ResearchRequest(BaseModel):
    niche: str = "Tech"

class ScriptRequest(BaseModel):
    topic: str
    niche: Optional[str] = "Tech"
    trend: Optional[dict] = None   # research topic card: why_trending, suggested_angle, evidence

class ExportXMLRequest(BaseModel):
    plan: dict

class VideoRequest(BaseModel):
    plan: dict                       # production plan { title, scenes[] } or a ScriptOutput
    mode: str = "personalised"       # "personalised" | "generic" (baseline)


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/health")
def health():
    return {
        "status": "ok",
        "llm_provider": os.getenv("LLM_PROVIDER", "ollama"),
        "groq_key_set": bool(os.getenv("GROQ_API_KEY")),
        "creator_profile_exists": PROFILE_PATH.exists(),
    }


# ── Task 1: Creator Profile ───────────────────────────────────────────────────

@app.get("/onboarding/profile")
def get_creator_profile(handle: str = "", niche: str = ""):
    """
    GET /onboarding/profile?handle=@creator&niche=Tech

    Reads the real creator_profile.json produced by Module 1 pipeline
    and returns it in the shape expected by the frontend DashboardScreen.

    Called by:
      - api.js processCreatorVideos() after mock steps complete
      - Any page refresh that needs to reload the profile
    """
    if not PROFILE_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="No creator profile found. Run Module 1 pipeline first: "
                   "cd module1_style_extraction && venv/Scripts/python main.py"
        )

    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    # Module 2's measured visual/audio stats (shot length, wpm, energy) when available
    if MULTIMODAL_PROFILE_PATH.exists():
        with open(MULTIMODAL_PROFILE_PATH, "r", encoding="utf-8") as f:
            multimodal = json.load(f)
        for key in ("visual_analysis", "audio_analysis", "_analyzed_videos"):
            if key in multimodal:
                raw[key] = multimodal[key]

    profile = _raw_profile_to_frontend(raw, handle=handle, niche=niche)
    return {"profile": profile}


# ── Task 2: Research (real YouTube Shorts data) ───────────────────────────────

def _trend_to_frontend(trend: dict, index: int, niche: str) -> dict:
    """Map a research_agent trend to the topic card shape the frontend renders."""
    signals = [trend["data_summary"]] + [
        f"\"{e['title'][:70]}\" — {e['channel']} · {e['views']:,} views "
        f"({e['outlier']:.1f}× subs) · {e['url']}"
        for e in trend["evidence"][:3]
    ]
    return {
        "id": f"t{index + 1}",
        "topic": trend["topic"],
        "niche": niche,
        # Both scores are measured (0-1), shown as /100 in the UI
        "trendScore": round(trend["trend_score"] * 100),
        "creatorFit": round(trend["creator_fit"] * 100),
        "signals": signals,
        "whyThis": trend["suggested_angle"] or trend["why_trending"] or trend["data_summary"],
        "lowConfidence": trend["low_confidence"],
        "evidence": trend["evidence"],
    }


@app.post("/research/trends")
def research_trends(body: ResearchRequest):
    """
    POST /research/trends  { niche: string }

    Runs the Research Agent: real YouTube Shorts → outlier/velocity scoring →
    MiniLM clustering → local-LLM labels. Scores come from measured data only.

    Returns: { topics: [ { id, topic, niche, trendScore, creatorFit, signals,
                           whyThis, lowConfidence, evidence } ], queries }
    """
    from pipeline.agents.research_agent import run_research

    creator_profile = {}
    if PROFILE_PATH.exists():
        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            creator_profile = json.load(f)

    try:
        result = run_research(creator_profile, body.niche)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Research failed: {e}")

    if not result["trends"]:
        raise HTTPException(status_code=503, detail=result["error"] or "No trends found.")

    return {
        "topics": [_trend_to_frontend(t, i, body.niche) for i, t in enumerate(result["trends"])],
        "queries": result["queries"],
    }


# ── Script Generation ─────────────────────────────────────────────────────────

@app.post("/script/generate")
def generate_scripts(body: ScriptRequest):
    """
    POST /script/generate  { topic, niche, trend? }

    Runs the Scripting Agent's full pipeline once per creator signature hook
    → 3 variants. Each is written in the creator's voice (real transcripts as
    examples), scored by the measured evaluator (style, timing, structure,
    hook rubric) and rewritten with concrete feedback when below threshold.

    `trend` is an optional research topic card (why_trending, suggested_angle,
    evidence) that gives the writer trend context.

    The A/B/C ablation (no_history vs retrieval_only vs full_pipeline) is a
    research experiment and lives in pipeline/test_scripting_comparison.py.
    """
    from pipeline.agents.scripting_agent import generate_variants, REGEN_THRESHOLD
    from pipeline.local_llm import LocalLLMError

    if not PROFILE_PATH.exists():
        raise HTTPException(status_code=400,
                            detail="No creator profile found. Run Module 1 pipeline first.")
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        creator_profile = json.load(f)

    try:
        results = generate_variants(body.topic, trend=body.trend, profile=creator_profile)
    except LocalLLMError as e:
        raise HTTPException(status_code=503, detail=f"LLM unavailable: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Script generation failed: {e}")

    variants = [_script_to_variant(script, meta, body.topic, i)
                for i, (script, meta) in enumerate(results)]
    passing = REGEN_THRESHOLD * 10
    return {
        "failed": all(v["overall"] is not None and v["overall"] < passing for v in variants),
        "variants": variants,
    }


# ── XML Export ────────────────────────────────────────────────────────────────

@app.post("/export/xml")
def export_xml(body: ExportXMLRequest):
    """
    POST /export/xml  { plan: { title, scenes[] } }

    Converts the production plan into a real Adobe Premiere Pro XMEML file
    using the existing json_to_premiere_xml.py pipeline module.
    """
    try:
        from pipeline.json_to_premiere_xml import build_xml, prettify_xml

        plan   = body.plan
        title  = plan.get("title", "ViralHook_Script")
        scenes = plan.get("scenes", [])

        if not scenes:
            raise HTTPException(status_code=400, detail="No scenes in production plan.")

        xml_scenes = [
            {
                "timecode":  f"{sc.get('startTime', '0:00')}-{sc.get('endTime', '0:05')}",
                "clip_idea": sc.get("visual", ""),
                "caption":   sc.get("caption", ""),
                "voiceover": sc.get("voiceover", ""),
            }
            for sc in scenes
        ]

        root    = build_xml(project_name=title, scenes=xml_scenes)
        xml_str = prettify_xml(root)
        return {"xml": xml_str}

    except HTTPException:
        raise
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Pipeline import error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Video Generation ──────────────────────────────────────────────────────────
# Renders take minutes and share one GPU, so jobs run one at a time on a
# single worker thread and the frontend polls /video/status/{job_id}.

_video_jobs: dict = {}
_video_lock = threading.Lock()
_video_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="video")


def _update_job(job_id: str, **fields):
    with _video_lock:
        _video_jobs[job_id].update(fields)


def _run_video_job(job_id: str, plan: dict, mode: str):
    from pipeline.agents.video_agent import generate_video, load_profile
    from pipeline.video.timeline import to_frontend

    _update_job(job_id, status="running")
    try:
        result = generate_video(
            plan, load_profile(), mode=mode, job_id=job_id,
            title=plan.get("title", "ViralHook"),
            on_step=lambda n, label, detail: _update_job(job_id, step=n, stepLabel=label, detail=detail),
        )
        _update_job(job_id, status="done", videoPath=result["video_path"],
                    timeline=to_frontend(result["timeline"]), evaluation=result["evaluation"],
                    seconds=result["seconds"])
    except Exception as e:
        _update_job(job_id, status="error", error=str(e))


@app.post("/video/generate")
def video_generate(body: VideoRequest):
    """
    POST /video/generate  { plan: { title, scenes[] }, mode? }

    Starts the Video Agent (voiceover → shots → assets → FFmpeg render →
    measured evaluation) in the background. Poll /video/status/{job_id}.
    """
    from pipeline.agents.video_agent import STEPS

    if body.mode not in ("personalised", "generic"):
        raise HTTPException(status_code=400, detail="mode must be 'personalised' or 'generic'")
    if not body.plan.get("scenes"):
        raise HTTPException(status_code=400, detail="No scenes in production plan.")

    job_id = uuid.uuid4().hex[:12]
    with _video_lock:
        _video_jobs[job_id] = {"jobId": job_id, "status": "queued", "mode": body.mode,
                               "step": 0, "stepLabel": "", "detail": "", "steps": STEPS}
    _video_executor.submit(_run_video_job, job_id, body.plan, body.mode)
    return {"jobId": job_id, "steps": STEPS}


@app.get("/video/status/{job_id}")
def video_status(job_id: str):
    """Progress while running; timeline + evaluation + videoUrl once done."""
    with _video_lock:
        job = dict(_video_jobs.get(job_id) or {})
    if not job:
        raise HTTPException(status_code=404, detail="Unknown video job.")
    job.pop("videoPath", None)
    if job["status"] == "done":
        job["videoUrl"] = f"/video/file/{job_id}"
    return job


@app.get("/video/file/{job_id}")
def video_file(job_id: str):
    with _video_lock:
        path = (_video_jobs.get(job_id) or {}).get("videoPath")
    if not path or not Path(path).exists():
        raise HTTPException(status_code=404, detail="Video not ready.")
    return FileResponse(path, media_type="video/mp4", filename=f"viralhook_{job_id}.mp4")
