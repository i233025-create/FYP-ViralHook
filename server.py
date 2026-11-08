"""
server.py — ViralHook PoC Backend
===================================
Every endpoint except /, /health and /auth/* needs a signed-in user, and works
on that user's own workspace (data/users/<id>/, see backend/workspace.py).

Endpoints:

  /auth/*                         → sign up, log in, sessions (backend/auth.py)
  GET  /health
  GET  /onboarding/profile        → reads creator_profile.json → frontend profile shape
  POST /onboarding/upload         → save videos, run Module 1 + 2 in background (returns job_id)
  GET  /onboarding/status/{job_id}→ extraction progress
  POST /research/trends           → Research Agent: trending topics from real YouTube Shorts
  POST /script/generate           → Scripting Agent: 3 hook variants, measured evaluator
  POST /export/xml                → Premiere Pro XML from production plan
  POST /assets/upload             → save the creator's photos for a video (returns library_id)
  GET  /assets/{lib}/file/{name}  → one uploaded photo
  POST /assets/match              → SigLIP suggestion per scene, for the creator to review (E3)
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
import shutil
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# ── Paths & env ───────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / "module1_style_extraction" / ".env")
load_dotenv(ROOT / ".env")

from backend import auth  # noqa: E402
from backend.config import get_settings  # noqa: E402
from backend.db import migrate  # noqa: E402
from backend.models import User  # noqa: E402
from backend.workspace import Workspace, child_dir, current_workspace  # noqa: E402

# ── App ───────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def _lifespan(_app: FastAPI):
    migrate()   # create / upgrade the product database (SQLite in development)
    yield


app = FastAPI(title="ViralHook API", version="0.2.0", lifespan=_lifespan)
auth.install_origin_guard(app)   # registered first, so it runs inside CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(get_settings().allowed_origins),
    allow_credentials=True,          # session cookies
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)


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
    assetLibraryId: Optional[str] = None            # from /assets/upload
    sceneAssets: Optional[dict[str, Optional[str]]] = None   # reviewed: scene index → photo name | null


class AssetMatchRequest(BaseModel):
    libraryId: str
    plan: dict


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/")
def root():
    """This is the API only; the UI is the Vite app (npm run dev → localhost:5173)."""
    return {"service": "ViralHook API", "ui": "http://localhost:5173", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "llm_provider": os.getenv("LLM_PROVIDER", "ollama"),
        "groq_key_set": bool(os.getenv("GROQ_API_KEY")),
    }


# ── Task 1: Creator Profile ───────────────────────────────────────────────────

@app.get("/onboarding/profile")
def get_creator_profile(handle: str = "", niche: str = "", ws: Workspace = Depends(current_workspace)):
    """
    GET /onboarding/profile?handle=@creator&niche=Tech

    Reads the real creator_profile.json produced by Module 1 pipeline
    and returns it in the shape expected by the frontend DashboardScreen.

    Called by:
      - api.js processCreatorVideos() after mock steps complete
      - Any page refresh that needs to reload the profile
    """
    paths = ws.creator
    if not paths.text_profile.exists():
        raise HTTPException(status_code=404, detail="No creator profile yet. Upload your videos to build one.")

    with open(paths.text_profile, "r", encoding="utf-8") as f:
        raw = json.load(f)
    # Module 2's measured visual/audio stats (shot length, wpm, energy) when available
    if paths.multimodal_profile.exists():
        with open(paths.multimodal_profile, "r", encoding="utf-8") as f:
            multimodal = json.load(f)
        for key in ("visual_analysis", "audio_analysis", "_analyzed_videos"):
            if key in multimodal:
                raw[key] = multimodal[key]

    profile = _raw_profile_to_frontend(raw, handle=handle, niche=niche)
    return {"profile": profile}


# ── Profile extraction from uploaded videos ──────────────────────────────────
# Upload replaces the user's current profile: their previous videos, ChromaDB
# and profiles move to <workspace>/archive/<timestamp>/ so one profile never
# mixes two sets of videos, and are restored if extraction fails. Module 1
# and Module 2 run as their own CLI subprocesses with VIRALHOOK_WORKSPACE set
# to the user's folder, on the GPU worker thread shared with video renders.

MODULE1_DIR = ROOT / "module1_style_extraction"
MODULE2_DIR = ROOT / "module2_multimodal_rag"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
MAX_UPLOAD_VIDEOS = 10

PROFILE_STEPS = [
    {"id": 1, "label": "Uploading videos"},
    {"id": 2, "label": "Transcribing & extracting text style (Module 1)"},
    {"id": 3, "label": "Building creator knowledge base"},
    {"id": 4, "label": "Visual & audio analysis (Module 2)"},
    {"id": 5, "label": "Generating creator profile"},
]

_profile_jobs: dict = {}
_profile_lock = threading.Lock()


def _update_profile_job(job_id: str, **fields):
    with _profile_lock:
        _profile_jobs[job_id].update(fields)


def _owned(jobs: dict, lock, job_id: str, user: User) -> dict:
    """A copy of the user's own job; someone else's job looks exactly like a missing one."""
    with lock:
        job = jobs.get(job_id)
        return dict(job) if job and job.get("ownerId") == user.id else {}


# Module 1 prints "STAGE 2 — Profile Extraction (Video 1/3)"; Module 2 prints
# a rule "Video 1/3: name.mp4" per video and "Synthesising ..." at the end.
_M1_STAGE = re.compile(r"STAGE (\d) — ([^(\n]+?)\s*\(Video (\d+)/(\d+)\)")
_M2_VIDEO = re.compile(r"Video (\d+)/(\d+): (\S+)")


def _run_module(job_id: str, cmd: list, cwd: Path, on_line, ws: Workspace):
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "COLUMNS": "200", "NO_COLOR": "1", **ws.subprocess_env()}
    log = []
    proc = subprocess.Popen(cmd, cwd=str(cwd), env=env, text=True, encoding="utf-8",
                            errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for line in proc.stdout:
        line = line.rstrip()
        if not line:
            continue
        log = (log + [line])[-40:]
        _update_profile_job(job_id, log=log)
        on_line(line)
    if proc.wait() != 0:
        tail = "\n".join(log[-8:])
        raise RuntimeError(f"{cmd[-1]} exited with code {proc.returncode}:\n{tail}")


def _run_profile_job(job_id: str, archive: Path, ws: Workspace):
    _update_profile_job(job_id, status="running", step=2, stepLabel=PROFILE_STEPS[1]["label"],
                        detail="Loading Whisper + LLM…")

    def module1_line(line: str):
        m = _M1_STAGE.search(line)
        if m:
            stage, name, i, n = m.groups()
            step = 3 if stage == "3" else 2
            _update_profile_job(job_id, step=step, stepLabel=PROFILE_STEPS[step - 1]["label"],
                                detail=f"Video {i}/{n} — {name.strip()}")
        elif "STAGE 4" in line:
            _update_profile_job(job_id, step=3, stepLabel=PROFILE_STEPS[2]["label"],
                                detail="RAG synthesis of the text profile")

    def module2_line(line: str):
        m = _M2_VIDEO.search(line)
        if m:
            i, n, name = m.groups()
            _update_profile_job(job_id, step=4, stepLabel=PROFILE_STEPS[3]["label"],
                                detail=f"Video {i}/{n} — {name} (CLIP, shots, audio)")
        elif "Synthesising Multimodal" in line:
            _update_profile_job(job_id, step=5, stepLabel=PROFILE_STEPS[4]["label"],
                                detail="Merging text + visual + audio stats")

    try:
        _run_module(job_id, [sys.executable, "-u", "main.py"], MODULE1_DIR, module1_line, ws)
        _update_profile_job(job_id, step=4, stepLabel=PROFILE_STEPS[3]["label"],
                            detail="Loading CLIP…")
        _run_module(job_id, [sys.executable, "-u", "module2_multimodal_rag/main.py"], ROOT,
                    module2_line, ws)
        if not ws.creator.text_profile.exists():
            raise RuntimeError("Module 1 finished but creator_profile.json was not written.")
        _update_profile_job(job_id, status="done", step=len(PROFILE_STEPS), detail="")
    except Exception as e:
        ws.restore_profile(archive)
        _update_profile_job(job_id, status="error",
                            error=f"{e}\n(Previous creator profile restored.)")


@app.post("/onboarding/upload")
def onboarding_upload(files: List[UploadFile] = File(...),
                      handle: str = Form(""), niche: str = Form(""),
                      user: User = Depends(auth.get_current_user),
                      ws: Workspace = Depends(current_workspace)):
    """
    POST /onboarding/upload  multipart: files[], handle, niche

    Saves the videos as the user's input_videos/ and starts Module 1 +
    Module 2 in the background. Poll /onboarding/status/{job_id}; when done,
    GET /onboarding/profile returns the freshly extracted profile.
    """
    videos = [f for f in files if Path(f.filename or "").suffix.lower() in VIDEO_EXTENSIONS]
    if not videos:
        raise HTTPException(status_code=400, detail="Upload at least one video "
                            f"({', '.join(sorted(VIDEO_EXTENSIONS))}).")
    if len(videos) > MAX_UPLOAD_VIDEOS:
        raise HTTPException(status_code=400, detail=f"At most {MAX_UPLOAD_VIDEOS} videos.")
    with _profile_lock:
        if any(j["status"] in ("queued", "running") and j["ownerId"] == user.id
               for j in _profile_jobs.values()):
            raise HTTPException(status_code=409, detail="Your profile is already being built.")
        job_id = uuid.uuid4().hex[:12]
        _profile_jobs[job_id] = {"jobId": job_id, "ownerId": user.id, "status": "queued", "step": 1,
                                 "stepLabel": PROFILE_STEPS[0]["label"], "detail": "",
                                 "steps": PROFILE_STEPS, "log": [],
                                 "handle": handle, "niche": niche}

    archive = ws.archive_profile(time.strftime("%Y%m%d-%H%M%S"))
    input_dir = ws.creator.input_videos
    try:
        input_dir.mkdir(parents=True)
        for i, up in enumerate(videos, start=1):
            safe = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(up.filename).name)
            with open(input_dir / f"{i:02d}_{safe}", "wb") as out:
                shutil.copyfileobj(up.file, out)
    except Exception as e:
        ws.restore_profile(archive)
        _update_profile_job(job_id, status="error", error=f"Saving uploads failed: {e}")
        raise HTTPException(status_code=500, detail=f"Saving uploads failed: {e}")
    _update_profile_job(job_id, detail=f"{len(videos)} video(s) saved")

    _video_executor.submit(_run_profile_job, job_id, archive, ws)
    return {"jobId": job_id, "steps": PROFILE_STEPS}


@app.get("/onboarding/status/{job_id}")
def onboarding_status(job_id: str, user: User = Depends(auth.get_current_user)):
    """Progress (step, detail, last log lines); status done → fetch /onboarding/profile."""
    job = _owned(_profile_jobs, _profile_lock, job_id, user)
    job.pop("ownerId", None)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown profile job.")
    return job


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
def research_trends(body: ResearchRequest, ws: Workspace = Depends(current_workspace)):
    """
    POST /research/trends  { niche: string }

    Runs the Research Agent: real YouTube Shorts → outlier/velocity scoring →
    MiniLM clustering → local-LLM labels. Scores come from measured data only.

    Returns: { topics: [ { id, topic, niche, trendScore, creatorFit, signals,
                           whyThis, lowConfidence, evidence } ], queries }
    """
    from pipeline.agents.research_agent import run_research

    creator_profile = {}
    if ws.creator.text_profile.exists():
        with open(ws.creator.text_profile, "r", encoding="utf-8") as f:
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
def generate_scripts(body: ScriptRequest, ws: Workspace = Depends(current_workspace)):
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

    if not ws.creator.text_profile.exists():
        raise HTTPException(status_code=400,
                            detail="No creator profile yet. Upload your videos to build one.")
    with open(ws.creator.text_profile, "r", encoding="utf-8") as f:
        creator_profile = json.load(f)

    try:
        results = generate_variants(body.topic, trend=body.trend, profile=creator_profile, paths=ws.creator)
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
def export_xml(body: ExportXMLRequest, user: User = Depends(auth.get_current_user)):
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


# ── Creator photos (E3): upload → SigLIP suggestions → creator review ─────────

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".jfif", ".bmp"}
MAX_UPLOAD_PHOTOS = 40
_asset_libraries: dict = {}            # library folder → CreatorAssetLibrary (embeddings stay in memory)
_asset_lock = threading.Lock()
_siglip = None                         # one SigLIP encoder shared by all libraries


def _library_dir(ws: Workspace, library_id: str) -> Path:
    """The user's own photo library; another user's id is simply unknown."""
    if not re.fullmatch(r"[0-9a-f]{12}", library_id or ""):
        raise HTTPException(status_code=400, detail="Bad asset library id.")
    folder = child_dir(ws.assets_dir, library_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="Unknown asset library.")
    return folder


def _get_library(ws: Workspace, library_id: str):
    """CreatorAssetLibrary for an uploaded set (cached, so photos are embedded once)."""
    global _siglip
    from pipeline.agents.video_agent import CACHE_DIR
    from pipeline.video.creator_assets import CreatorAssetLibrary, SiglipEncoder

    folder = _library_dir(ws, library_id)
    key = str(folder)
    with _asset_lock:
        if key not in _asset_libraries:
            _siglip = _siglip or SiglipEncoder()
            _asset_libraries[key] = CreatorAssetLibrary(folder, CACHE_DIR, encoder=_siglip)
        return _asset_libraries[key]


def _photo_list(library_id: str, folder: Path) -> list[dict]:
    return [{"name": p.name, "url": f"/assets/{library_id}/file/{p.name}"}
            for p in sorted(folder.iterdir()) if p.suffix.lower() in IMAGE_EXTENSIONS]


@app.post("/assets/upload")
def assets_upload(files: List[UploadFile] = File(...), ws: Workspace = Depends(current_workspace)):
    """
    POST /assets/upload  multipart: files[]  (the creator's photos for this video)
    → { libraryId, photos: [{name, url}] }
    """
    photos = [f for f in files if Path(f.filename or "").suffix.lower() in IMAGE_EXTENSIONS]
    if not photos:
        raise HTTPException(status_code=400, detail="Upload at least one photo "
                            f"({', '.join(sorted(IMAGE_EXTENSIONS))}).")
    if len(photos) > MAX_UPLOAD_PHOTOS:
        raise HTTPException(status_code=400, detail=f"At most {MAX_UPLOAD_PHOTOS} photos.")
    library_id = uuid.uuid4().hex[:12]
    folder = ws.assets_dir / library_id
    folder.mkdir(parents=True)
    for i, up in enumerate(photos, start=1):
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(up.filename).name)
        with open(folder / f"{i:02d}_{safe}", "wb") as out:
            shutil.copyfileobj(up.file, out)
    return {"libraryId": library_id, "photos": _photo_list(library_id, folder)}


@app.get("/assets/{library_id}/file/{name}")
def assets_file(library_id: str, name: str, ws: Workspace = Depends(current_workspace)):
    folder = _library_dir(ws, library_id)
    path = folder / Path(name).name
    if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
        raise HTTPException(status_code=404, detail="Photo not found.")
    return FileResponse(path)


@app.post("/assets/match")
def assets_match(body: AssetMatchRequest, ws: Workspace = Depends(current_workspace)):
    """
    POST /assets/match { libraryId, plan }
    → { threshold, photos, scenes: [{index, segment, clipIdea, ranked[{name, score}], suggested}] }
    Scene indices match the Video Agent's (scenes without voiceover are skipped).
    """
    from pipeline.video.timeline import normalize_scenes

    library = _get_library(ws, body.libraryId)
    try:
        scenes = normalize_scenes(body.plan)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        suggestions = library.suggest([sc["clip_idea"] or sc["voiceover"] for sc in scenes])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Photo matching failed: {e}")
    return {
        "threshold": library.threshold,
        "photos": _photo_list(body.libraryId, library.folder),
        "scenes": [{"index": i, "segment": sc["segment"], "clipIdea": sc["clip_idea"], **sug}
                   for i, (sc, sug) in enumerate(zip(scenes, suggestions))],
    }


def _run_video_job(job_id: str, plan: dict, mode: str, ws: Workspace, library_id: str | None = None,
                   scene_assets: dict | None = None):
    from pipeline.agents.video_agent import generate_video, load_profile
    from pipeline.video.creator_visual import load_creator_visual
    from pipeline.video.timeline import to_frontend

    _update_job(job_id, status="running")
    try:
        result = generate_video(
            plan, load_profile(ws.creator), mode=mode, job_id=job_id,
            out_dir=ws.videos_dir / job_id,
            title=plan.get("title", "ViralHook"),
            on_step=lambda n, label, detail: _update_job(job_id, step=n, stepLabel=label, detail=detail),
            creator=load_creator_visual(ws.creator.qdrant_snapshot),
            assets=_get_library(ws, library_id) if library_id else None,
            scene_assets={int(k): v for k, v in scene_assets.items()} if scene_assets is not None else None,
        )
        _update_job(job_id, status="done", videoPath=result["video_path"],
                    timeline=to_frontend(result["timeline"]), evaluation=result["evaluation"],
                    seconds=result["seconds"])
    except Exception as e:
        _update_job(job_id, status="error", error=str(e))


@app.post("/video/generate")
def video_generate(body: VideoRequest, user: User = Depends(auth.get_current_user),
                   ws: Workspace = Depends(current_workspace)):
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

    if body.assetLibraryId:
        _library_dir(ws, body.assetLibraryId)   # 400/404 now rather than inside the job
    job_id = uuid.uuid4().hex[:12]
    with _video_lock:
        _video_jobs[job_id] = {"jobId": job_id, "ownerId": user.id, "status": "queued", "mode": body.mode,
                               "step": 0, "stepLabel": "", "detail": "", "steps": STEPS}
    _video_executor.submit(_run_video_job, job_id, body.plan, body.mode, ws,
                           body.assetLibraryId, body.sceneAssets)
    return {"jobId": job_id, "steps": STEPS}


@app.get("/video/status/{job_id}")
def video_status(job_id: str, user: User = Depends(auth.get_current_user)):
    """Progress while running; timeline + evaluation + videoUrl once done."""
    job = _owned(_video_jobs, _video_lock, job_id, user)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown video job.")
    job.pop("videoPath", None)
    job.pop("ownerId", None)
    if job["status"] == "done":
        job["videoUrl"] = f"/video/file/{job_id}"
    return job


@app.get("/video/file/{job_id}")
def video_file(job_id: str, user: User = Depends(auth.get_current_user)):
    path = _owned(_video_jobs, _video_lock, job_id, user).get("videoPath")
    if not path or not Path(path).exists():
        raise HTTPException(status_code=404, detail="Video not ready.")
    return FileResponse(path, media_type="video/mp4", filename=f"viralhook_{job_id}.mp4")
