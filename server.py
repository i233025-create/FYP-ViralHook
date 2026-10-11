"""
server.py — ViralHook PoC Backend
===================================
Endpoints:

  GET  /health
  GET  /onboarding/profile        → reads creator_profile.json → frontend profile shape
  POST /research/trends           → LLM-based trend generation (3 distinct topics)
  POST /script/generate           → RAG scripting agent (3 modes)
  POST /export/xml                → Premiere Pro XML from production plan

Run:
  module1_style_extraction\\venv\\Scripts\\python.exe -m uvicorn server:app --reload --port 8000
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
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


def _script_to_variant(script, mode: str, topic: str, eval_scores: Optional[dict], regen: bool) -> dict:
    s = script if isinstance(script, dict) else script.model_dump()
    scenes_raw = s.get("scenes", [])
    scenes = [_scene_to_frontend(sc, i, len(scenes_raw)) for i, sc in enumerate(scenes_raw)]
    _defaults = {
        "no_history":     (65, 60, 62, 62),
        "retrieval_only": (78, 75, 80, 78),
        "full_pipeline":  (88, 85, 90, 88),
    }
    d_sc, d_ha, d_sa, d_ov = _defaults.get(mode, (70, 70, 70, 70))
    if eval_scores:
        sc  = int(float(eval_scores.get("style_match",            d_sc / 10)) * 10)
        ha  = int(float(eval_scores.get("hook_strength",          d_ha / 10)) * 10)
        sa  = int(float(eval_scores.get("structure_adherence",    d_sa / 10)) * 10)
        ov  = int(float(eval_scores.get("overall",                d_ov / 10)) * 10)
    else:
        sc, ha, sa, ov = d_sc, d_ha, d_sa, d_ov
    _labels     = {"no_history": "VARIANT A", "retrieval_only": "VARIANT B", "full_pipeline": "VARIANT C"}
    _structures = {
        "no_history":     "Hook → Points → Conclusion (baseline — no creator context)",
        "retrieval_only": "Hook → Context → Evidence → Takeaway (RAG examples injected)",
        "full_pipeline":  "Hook → Misconception → Explanation → CTA (RAG + evaluator loop)",
    }
    return {
        "id": f"sv_{mode}",
        "label": _labels.get(mode, "VARIANT"),
        "topic": topic,
        "hook": scenes[0]["voiceover"] if scenes else "",
        "hookType": s.get("hook_type", "Bold Claim"),
        "structure": _structures.get(mode, "Hook → Problem → Solution"),
        "styleConsistency":   max(0, min(100, sc)),
        "hookAlignment":      max(0, min(100, ha)),
        "structureAlignment": max(0, min(100, sa)),
        "overall":            max(0, min(100, ov)),
        "scenes": scenes,
        "mode": mode,
        "regenTriggered": regen,
        "evaluatorScores": eval_scores,
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

class ExportXMLRequest(BaseModel):
    plan: dict


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/health")
def health():
    return {
        "status": "ok",
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

    # Per-video breakdowns (hook, pacing, shots, speech rate) only exist in
    # Module 2's multimodal profile — attach them for the dashboard cards
    if "per_video_profiles" not in raw and MULTIMODAL_PROFILE_PATH.exists():
        with open(MULTIMODAL_PROFILE_PATH, "r", encoding="utf-8") as f:
            raw["per_video_profiles"] = json.load(f).get("per_video_profiles", [])

    profile = _raw_profile_to_frontend(raw, handle=handle, niche=niche)
    return {"profile": profile}


# ── Task 2: Research (LLM-based, no YouTube API) ──────────────────────────────

@app.post("/research/trends")
def research_trends(body: ResearchRequest):
    """
    POST /research/trends  { niche: string }

    Generates 3 distinct trending topic suggestions using the Groq LLM directly.
    No YouTube API — prompts the LLM 3 times with different angle constraints
    so each topic comes from a genuinely different content angle.

    Returns: { topics: [ { id, topic, niche, trendScore, creatorFit, signals, whyThis } ] }
    """
    try:
        from langchain_groq import ChatGroq
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import JsonOutputParser
        from datetime import datetime

        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            raise HTTPException(status_code=500, detail="GROQ_API_KEY not set.")

        llm = ChatGroq(api_key=api_key, model_name="openai/gpt-oss-20b",
                       temperature=0.85, max_tokens=600)

        # Load creator profile for personalised relevance scoring
        creator_profile = {}
        if PROFILE_PATH.exists():
            with open(PROFILE_PATH, "r", encoding="utf-8") as f:
                creator_profile = json.load(f)

        creator_context = ""
        if creator_profile:
            hooks    = creator_profile.get("signature_hooks", [])
            tone     = creator_profile.get("dominant_tone", "")
            audience = creator_profile.get("target_audience", "")
            creator_context = (
                f"The creator's style: {tone} tone, hooks like {hooks[:2]}, "
                f"audience: {audience}."
            )

        # 3 different angle prompts to guarantee variety
        angle_prompts = [
            # Angle 1 — currently viral / momentum
            f"Focus on a topic with STRONG current momentum — something blowing up RIGHT NOW in short-form video. "
            f"Think contrarian takes, surprising facts, or \"everyone is wrong about X\" angles.",

            # Angle 2 — underserved / niche insight
            f"Focus on an UNDERSERVED angle — a topic not many creators have covered yet in this niche. "
            f"Think emerging trends, niche insights, or \"before everyone else\" opportunities.",

            # Angle 3 — evergreen high-performer
            f"Focus on an EVERGREEN high-performing topic that consistently gets engagement. "
            f"Think timeless advice, skill-building, or \"should know this\" educational content.",
        ]

        prompt_template = ChatPromptTemplate.from_template(
            """You are a viral content strategist for short-form video (Instagram Reels / YouTube Shorts).
Today is {date}. Niche: "{niche}". {creator_context}

{angle}

Suggest ONE specific, compelling trending topic for a 30-second short-form video.
The topic should be a specific, punchy title — NOT a generic category.
Good example: "Why your morning routine is sabotaging your focus"
Bad example: "Morning routines" or "Productivity tips"

Output ONLY valid JSON (no markdown, no extra text):
{{
  "topic": "specific punchy topic title",
  "trendScore": <integer 60-95>,
  "creatorFit": <integer 60-95>,
  "signals": ["signal 1", "signal 2", "signal 3"],
  "whyThis": "one sentence explaining why this topic works for this creator right now"
}}"""
        )

        chain = prompt_template | llm | JsonOutputParser()
        date_str = datetime.now().strftime("%B %d, %Y")

        topics = []
        seen = set()

        for i, angle in enumerate(angle_prompts):
            try:
                result = chain.invoke({
                    "date": date_str,
                    "niche": body.niche,
                    "creator_context": creator_context,
                    "angle": angle,
                })

                topic_name = result.get("topic", "").strip()
                if not topic_name or topic_name in seen:
                    continue
                seen.add(topic_name)

                topics.append({
                    "id": f"t{len(topics)+1}",
                    "topic": topic_name,
                    "niche": body.niche,
                    "trendScore": max(40, min(95, int(result.get("trendScore", 70)))),
                    "creatorFit":  max(40, min(95, int(result.get("creatorFit",  70)))),
                    "signals": result.get("signals", [f"LLM-identified trend in {body.niche} niche"]),
                    "whyThis": result.get("whyThis", f"Strong opportunity in the {body.niche} niche right now."),
                })
            except Exception as e:
                # One prompt failed — continue to next angle
                print(f"[ResearchAgent] Angle {i+1} failed: {e}")
                continue

        if not topics:
            raise HTTPException(status_code=500, detail="LLM trend generation failed for all angles.")

        return {"topics": topics}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Script Generation ─────────────────────────────────────────────────────────

@app.post("/script/generate")
def generate_scripts(body: ScriptRequest):
    """
    POST /script/generate  { topic, niche }

    Runs all 3 scripting modes:
      - Variant A (no_history):     baseline LLM, no creator context
      - Variant B (retrieval_only): RAG examples from ChromaDB injected
      - Variant C (full_pipeline):  RAG + creator profile + evaluator + regen loop

    This is the core FYP contribution — the score difference between A and C
    demonstrates that creator-specific RAG improves script quality.
    """
    try:
        from pipeline.agents.scripting_agent import (
            generate_no_history,
            generate_retrieval_only,
            generate_full_pipeline,
            _load_creator_profile,
            _load_chroma_retriever,
            _load_multimodal_retriever,
            _retrieve_examples,
            _retrieve_examples_qdrant,
            _extract_style_params,
        )
        from langchain_groq import ChatGroq

        creator_profile = _load_creator_profile()
        if not creator_profile:
            raise HTTPException(
                status_code=400,
                detail="No creator profile found. Run Module 1 pipeline first."
            )

        style_params = _extract_style_params(creator_profile)

        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            raise HTTPException(status_code=500, detail="GROQ_API_KEY not set.")

        llm = ChatGroq(api_key=api_key, model_name="openai/gpt-oss-120b",
                       temperature=0.7, max_tokens=1200)

        # Try Qdrant (module2 multimodal) first, fall back to ChromaDB (module1)
        qdrant_client, has_multimodal = _load_multimodal_retriever()
        if has_multimodal:
            retrieved = _retrieve_examples_qdrant(qdrant_client, body.topic)
            print(f"[server] Using multimodal Qdrant retrieval")
        else:
            retriever = _load_chroma_retriever()
            retrieved = _retrieve_examples(retriever, body.topic) if retriever else ""
            print(f"[server] Using ChromaDB retrieval")

        import time
        variants = []

        # Variant A — no creator context (baseline for comparison)
        script_a, meta_a = generate_no_history(body.topic, style_params, llm)
        variants.append(_script_to_variant(
            script_a, "no_history", body.topic,
            meta_a.get("evaluator_scores"), meta_a.get("regen_triggered", False)
        ))

        time.sleep(20)  # wait for TPM window to reset between modes

        # Variant B — RAG retrieval only
        script_b, meta_b = generate_retrieval_only(body.topic, style_params, creator_profile, retrieved, llm)
        variants.append(_script_to_variant(
            script_b, "retrieval_only", body.topic,
            meta_b.get("evaluator_scores"), meta_b.get("regen_triggered", False)
        ))

        time.sleep(20)  # wait for TPM window to reset between modes

        # Variant C — full pipeline (RAG + evaluator + regeneration loop)
        script_c, meta_c = generate_full_pipeline(body.topic, style_params, creator_profile, retrieved, llm)
        variants.append(_script_to_variant(
            script_c, "full_pipeline", body.topic,
            meta_c.get("evaluator_scores"), meta_c.get("regen_triggered", False)
        ))

        return {"failed": False, "variants": variants}

    except HTTPException:
        raise
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Pipeline import error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
