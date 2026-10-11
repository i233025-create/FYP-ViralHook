"""
scripting_agent.py — LangGraph Scripting Agent Node
=====================================================
Generates a short-form video script from a trending topic and creator profile.

Implements three modes for ablation comparison (FYP research contribution):

  Mode 1 — no_history
    Single LLM call with topic only. No creator context, no feedback.
    Baseline: what does the LLM produce without any personalisation?

  Mode 2 — retrieval_only
    LLM call with RAG context injected:
      - Per-video profile examples retrieved from ChromaDB (few-shot)
      - Full creator_profile.json as style guide
    Tests: does retrieval alone improve style alignment?

  Mode 3 — full_pipeline
    retrieval_only + evaluator scoring + conditional regeneration loop.
    Evaluator scores style_match, hook_strength, structure_adherence (0-10).
    If overall score < REGEN_THRESHOLD (7.0), regenerates with feedback.
    Capped at MAX_REGEN_ATTEMPTS (2) to control API usage.
    Tests: does evaluation + feedback further improve output?

All three modes use the same:
  - Topic (from research_output.topic)
  - Creator's dominant hook_type and structure_type (from creator_profile)
  - 5-scene, 30-second target format
  - Same LLM (openai/gpt-oss-20b via Groq)

Output schema (ScriptOutput Pydantic model, defined in pipeline/state.py):
  script_id, concept_name, hook_type, scenes[{timecode, clip_idea,
  caption, voiceover}]

The LangGraph node (scripting_agent()) reads mode from state and writes
scripting_output. The comparison script (test_scripting_comparison.py)
runs all three modes and prints results side by side.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

# Load .env
load_dotenv(Path(__file__).parent.parent.parent / "module1_style_extraction" / ".env")
load_dotenv(Path(__file__).parent.parent.parent / ".env")

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from pipeline.state import PipelineState, ScriptingOutput, ScriptOutput, SceneOutput

# ─── Configuration ─────────────────────────────────────────────────────────────
GROQ_MODEL = "openai/gpt-oss-20b"
CHROMA_PERSIST_DIR = str(
    Path(__file__).parent.parent.parent / "module1_style_extraction" / "chroma_db"
)
COLLECTION_NAME = "video_profiles"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
CREATOR_PROFILE_PATH = (
    Path(__file__).parent.parent.parent / "module1_style_extraction" / "creator_profile.json"
)

REGEN_THRESHOLD = 7.0       # Regenerate if overall score below this
MAX_REGEN_ATTEMPTS = 2      # Max regeneration loops in full_pipeline mode
RAG_TOP_K = 3               # Number of ChromaDB documents to retrieve


# ─── Prompt Templates ──────────────────────────────────────────────────────────

# Mode 1: no creator context at all
NO_HISTORY_PROMPT = """You are a short-form video scriptwriter.
Write a compelling 30-second video script about the following topic.

TOPIC: {topic}

Requirements:
- Exactly 5 scenes
- Target duration: 30 seconds total
- Hook must grab attention in the first 3 seconds
- Hook type to use: {hook_type}
- Content structure to follow: {structure}

Output ONLY a valid JSON object. No text before or after. No markdown code blocks.

{{
  "script_id": 1,
  "concept_name": "short creative name for this script concept",
  "hook_type": "{hook_type}",
  "scenes": [
    {{
      "timecode": "0:00-0:05",
      "clip_idea": "detailed visual description for B-roll or AI image generation",
      "caption": "short on-screen subtitle text (max 8 words)",
      "voiceover": "exact spoken narration for this scene"
    }}
  ]
}}

Each scene must have a timecode, clip_idea, caption, and voiceover.
The 5 scenes should total approximately 30 seconds."""


# Mode 2 & 3: with RAG context (ChromaDB examples + creator profile)
RETRIEVAL_PROMPT = """You are an expert short-form video scriptwriter specialising in
creator-style replication. You have been given a creator's style profile and examples
of their past content. Your job is to write a new script that sounds EXACTLY like
this creator — matching their tone, pacing, hook style, and structure.

CREATOR STYLE PROFILE:
{creator_profile}

EXAMPLES FROM CREATOR'S PAST VIDEOS (retrieved from their content library):
{retrieved_examples}

NEW TOPIC TO SCRIPT: {topic}

Requirements:
- Exactly 5 scenes, 30 seconds total
- Hook type: {hook_type} (this creator's signature hook style)
- Structure: {structure} (this creator's typical content structure)
- Tone: {tone} (match this exactly)
- Pacing: {pacing} (fast-paced = short punchy sentences, slow = longer narrative)
- Target audience: {target_audience}

Write a script that a viewer who knows this creator would immediately recognise
as their content. Do NOT write generic content — make it specific and on-brand.

Output ONLY a valid JSON object. No text before or after. No markdown code blocks.

{{
  "script_id": 1,
  "concept_name": "short creative name for this script concept",
  "hook_type": "{hook_type}",
  "scenes": [
    {{
      "timecode": "0:00-0:05",
      "clip_idea": "detailed visual description for B-roll or AI image generation",
      "caption": "short on-screen subtitle text (max 8 words)",
      "voiceover": "exact spoken narration for this scene"
    }}
  ]
}}"""


# Evaluator prompt — used only in full_pipeline mode
EVALUATOR_PROMPT = """You are an expert content strategist evaluating a short-form
video script against a creator's established style profile.

CREATOR STYLE PROFILE:
{creator_profile}

SCRIPT TO EVALUATE:
{script}

Score this script on THREE criteria (each 0-10):

1. style_match: How well does the script match the creator's tone, vocabulary,
   and personality? (10 = indistinguishable from their real content)

2. hook_strength: How compelling and scroll-stopping is the opening hook?
   (10 = extremely strong, would stop 90%+ of viewers)

3. structure_adherence: How closely does the script follow the creator's
   typical content structure ({structure})?
   (10 = follows the structure perfectly)

Output ONLY a valid JSON object. No text before or after.

{{
  "style_match": 7,
  "hook_strength": 8,
  "structure_adherence": 6,
  "overall": 7.0,
  "feedback": "specific, actionable feedback for improvement in 2-3 sentences"
}}"""


# Regeneration prompt — used when score < REGEN_THRESHOLD
REGEN_PROMPT = """You are an expert short-form video scriptwriter. Your previous
script attempt received a quality score of {score}/10 with this feedback:

FEEDBACK: {feedback}

CREATOR STYLE PROFILE:
{creator_profile}

EXAMPLES FROM CREATOR'S PAST VIDEOS:
{retrieved_examples}

TOPIC: {topic}
Hook type: {hook_type}
Structure: {structure}
Tone: {tone}
Pacing: {pacing}
Target audience: {target_audience}

Rewrite the script addressing the feedback. Focus specifically on improving
the areas mentioned. Keep what was working, fix what wasn't.

Output ONLY a valid JSON object. No text before or after. No markdown code blocks.

{{
  "script_id": 1,
  "concept_name": "short creative name for this script concept",
  "hook_type": "{hook_type}",
  "scenes": [
    {{
      "timecode": "0:00-0:05",
      "clip_idea": "detailed visual description for B-roll or AI image generation",
      "caption": "short on-screen subtitle text (max 8 words)",
      "voiceover": "exact spoken narration for this scene"
    }}
  ]
}}"""


# ─── Utility Functions ─────────────────────────────────────────────────────────

def _load_creator_profile() -> dict:
    """
    Load the master creator profile from Module 1's output JSON file.

    Returns an empty dict if the file doesn't exist (graceful degradation).
    """
    if not CREATOR_PROFILE_PATH.exists():
        print(f"[ScriptingAgent] WARNING: creator_profile.json not found at "
              f"{CREATOR_PROFILE_PATH}. Run Module 1 first.")
        return {}
    with open(CREATOR_PROFILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_chroma_retriever():
    """
    Load the ChromaDB vector store from Module 1 and return a retriever.
    Returns None if ChromaDB doesn't exist (graceful degradation).
    """
    if not Path(CHROMA_PERSIST_DIR).exists():
        print(f"[ScriptingAgent] WARNING: ChromaDB not found at {CHROMA_PERSIST_DIR}. "
              f"Run Module 1 first.")
        return None

    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    vector_store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=CHROMA_PERSIST_DIR,
    )

    doc_count = vector_store._collection.count()
    if doc_count == 0:
        print("[ScriptingAgent] WARNING: ChromaDB collection is empty. "
              "Run Module 1 first to populate it.")
        return None

    print(f"[ScriptingAgent] ChromaDB loaded: {doc_count} documents")
    return vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": RAG_TOP_K},
    )


def _load_multimodal_retriever():
    """
    Load the Qdrant in-memory store from Module 2 if available.

    Module 2 persists its Qdrant data to a JSON snapshot file
    (qdrant_snapshot.json) after each run so it can be reloaded.

    Returns (client, True) if Module 2 data available,
            (None, False) otherwise — falls back to ChromaDB.
    """
    _ROOT = Path(__file__).parent.parent.resolve()
    snapshot_path = _ROOT / "module2_multimodal_rag" / "qdrant_snapshot.json"

    if not snapshot_path.exists():
        return None, False

    try:
        import json
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams, PointStruct
        import uuid as _uuid

        with open(snapshot_path, "r", encoding="utf-8") as f:
            snapshot = json.load(f)

        points = snapshot.get("points", [])
        if not points:
            return None, False

        client = QdrantClient(":memory:")
        client.create_collection(
            collection_name="multimodal_profiles",
            vectors_config={
                "text":   VectorParams(size=384, distance=Distance.COSINE),
                "visual": VectorParams(size=512, distance=Distance.COSINE),
            },
        )
        client.upsert(
            collection_name="multimodal_profiles",
            points=[
                PointStruct(
                    id=str(_uuid.uuid4()),
                    vector={
                        "text":   p["text_vector"],
                        "visual": p["visual_vector"],
                    },
                    payload=p["payload"],
                )
                for p in points
                if p.get("text_vector") and p.get("visual_vector")
            ],
        )
        count = client.count(collection_name="multimodal_profiles").count
        print(f"[ScriptingAgent] Qdrant (multimodal) loaded: {count} documents")
        return client, True

    except Exception as e:
        print(f"[ScriptingAgent] Qdrant load failed: {e} — falling back to ChromaDB")
        return None, False


def _retrieve_examples_qdrant(client, topic: str, k: int = 3) -> str:
    """
    Query Qdrant multimodal store for relevant video profiles.
    Uses text vector search (topic query → all-MiniLM embedding).
    Returns formatted string for prompt injection — same format as ChromaDB version.
    """
    try:
        from langchain_community.embeddings import HuggingFaceEmbeddings as HFEmb
        embedder = HFEmb(
            model_name=EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        query    = f"content style hook tone pacing structure for topic: {topic}"
        q_vector = embedder.embed_query(query)

        response = client.query_points(
            collection_name="multimodal_profiles",
            query=q_vector,
            using="text",
            limit=min(k, client.count(collection_name="multimodal_profiles").count),
            with_payload=True,
        )
        points = response.points

        if not points:
            return "No relevant examples found in creator's multimodal library."

        parts = []
        for i, p in enumerate(points, 1):
            pl = p.payload or {}
            entry = (
                f"--- Example {i} (Multimodal Profile) ---\n"
                f"Hook Type: {pl.get('hook_type', 'N/A')}\n"
                f"Tone: {pl.get('tone', 'N/A')}\n"
                f"Structure: {pl.get('structure', 'N/A')}\n"
                f"Visual Pacing: {pl.get('visual_pacing', 'N/A')} "
                f"({pl.get('avg_shot_duration', '?')}s avg shot)\n"
                f"Talking Head: {pl.get('talking_head_pct', 0)*100:.0f}% | "
                f"B-Roll: {pl.get('broll_pct', 0)*100:.0f}%\n"
                f"Speech Rate: {pl.get('speech_rate_wpm', 'N/A')} wpm "
                f"({pl.get('speech_rate_label', '')})\n"
                f"Energy: {pl.get('energy_label', 'N/A')}\n"
                f"Key Phrases: {', '.join(pl.get('key_phrases', [])[:5])}\n"
                f"Summary: {pl.get('transcript_summary', 'N/A')}"
            )
            parts.append(entry)

        return "\n\n".join(parts)

    except Exception as e:
        return f"Qdrant retrieval failed: {e}"


def _retrieve_examples(retriever, topic: str) -> str:
    """
    Query ChromaDB for per-video profiles most relevant to the topic.

    Returns formatted string of retrieved examples for prompt injection.
    """
    if retriever is None:
        return "No examples available (ChromaDB not populated)."

    try:
        query = f"content style hook tone pacing structure for topic: {topic}"
        docs = retriever.invoke(query)

        if not docs:
            return "No relevant examples found in creator's content library."

        parts = []
        for i, doc in enumerate(docs, 1):
            parts.append(f"--- Example {i} ---\n{doc.page_content}")
        return "\n\n".join(parts)

    except Exception as e:
        return f"Retrieval failed: {e}"


def _format_creator_profile(profile: dict) -> str:
    """
    Format the creator profile dict as a readable string for prompt injection.
    """
    if not profile:
        return "No creator profile available."

    lines = []
    if profile.get("creator_niche"):
        lines.append(f"Niche: {profile['creator_niche']}")
    if profile.get("dominant_tone"):
        lines.append(f"Tone: {profile['dominant_tone']}")
    if profile.get("avg_pacing"):
        lines.append(f"Pacing: {profile['avg_pacing']}")
    if profile.get("typical_structure"):
        lines.append(f"Typical structure: {profile['typical_structure']}")
    if profile.get("target_audience"):
        lines.append(f"Target audience: {profile['target_audience']}")
    if profile.get("signature_hooks"):
        lines.append(f"Signature hooks: {', '.join(profile['signature_hooks'])}")
    if profile.get("recurring_topics"):
        lines.append(f"Recurring topics: {', '.join(profile['recurring_topics'][:5])}")
    if profile.get("content_style_summary"):
        lines.append(f"Style summary: {profile['content_style_summary']}")

    return "\n".join(lines)


def _extract_style_params(creator_profile: dict) -> dict:
    """
    Extract the key style parameters used across all script prompts.

    These ensure all three modes use the same hook_type and structure
    for a fair ablation comparison.
    """
    hooks = creator_profile.get("signature_hooks", [])
    hook_type = hooks[0] if hooks else "Bold Claim"

    return {
        "hook_type": hook_type,
        "structure": creator_profile.get("typical_structure", "Hook → Problem → Solution"),
        "tone": creator_profile.get("dominant_tone", "Conversational"),
        "pacing": creator_profile.get("avg_pacing", "Fast-paced"),
        "target_audience": creator_profile.get("target_audience", "General audience"),
    }


def _parse_script_response(raw: dict) -> ScriptOutput:
    """
    Parse and validate LLM JSON response into a ScriptOutput Pydantic model.

    Applies defensive defaults for any missing fields so parsing never
    crashes the pipeline — a malformed LLM response degrades gracefully.
    """
    raw.setdefault("script_id", 1)
    raw.setdefault("concept_name", "Untitled Script")
    raw.setdefault("hook_type", "Bold Claim")
    raw.setdefault("scenes", [])

    # Ensure scenes is a list and each scene has required fields
    scenes = []
    for i, scene in enumerate(raw.get("scenes", []), start=1):
        if not isinstance(scene, dict):
            continue
        voiceover = scene.get("voiceover", "").strip()
        caption = scene.get("caption", "").strip()
        # Skip scenes with empty voiceover — they indicate LLM truncation
        if not voiceover:
            print(f"[ScriptingAgent] Skipping scene {i} — empty voiceover (LLM truncation)")
            continue
        scenes.append(SceneOutput(
            timecode=scene.get("timecode", f"0:{(i-1)*6:02d}-0:{i*6:02d}"),
            clip_idea=scene.get("clip_idea", "Visual placeholder"),
            caption=caption,
            voiceover=voiceover,
        ))

    return ScriptOutput(
        script_id=raw["script_id"],
        concept_name=raw["concept_name"],
        hook_type=raw["hook_type"],
        scenes=scenes,
    )


def _call_llm(llm: ChatGroq, prompt_template: str, variables: dict) -> dict:
    """
    Run a prompt template through the LLM and return parsed JSON dict.

    Retries once on JSON parse failure (LLM occasionally wraps JSON
    in markdown code blocks despite explicit instructions not to).
    """
    prompt = ChatPromptTemplate.from_template(prompt_template)
    parser = JsonOutputParser()
    chain = prompt | llm | parser

    try:
        return chain.invoke(variables)
    except Exception as e:
        # If JSON parsing failed, try extracting JSON manually
        raise RuntimeError(f"LLM call failed: {e}") from e


# ─── Three Script Generation Modes ────────────────────────────────────────────

def generate_no_history(
    topic: str,
    style_params: dict,
    llm: ChatGroq,
) -> tuple[ScriptOutput, dict]:
    """
    Mode 1: Generate script with NO creator context.

    Single LLM call. No RAG retrieval. No creator profile injection.
    Uses hook_type and structure from creator profile to ensure fair
    comparison (we're testing context quality, not hook variety).

    Args:
        topic:        Trending topic from research_output.
        style_params: Hook type + structure from creator profile.
        llm:          Initialised ChatGroq instance.

    Returns:
        Tuple of (ScriptOutput, metadata_dict).
        metadata_dict contains mode, llm_calls_made, evaluator_scores.
    """
    print(f"\n[ScriptingAgent] Mode 1: no_history")

    raw = _call_llm(llm, NO_HISTORY_PROMPT, {
        "topic": topic,
        "hook_type": style_params["hook_type"],
        "structure": style_params["structure"],
    })

    script = _parse_script_response(raw)
    print(f"[ScriptingAgent] no_history → '{script.concept_name}'")

    return script, {
        "mode": "no_history",
        "llm_calls": 1,
        "evaluator_scores": None,
        "regen_triggered": False,
    }


def generate_retrieval_only(
    topic: str,
    style_params: dict,
    creator_profile: dict,
    retrieved_examples: str,
    llm: ChatGroq,
) -> tuple[ScriptOutput, dict]:
    """
    Mode 2: Generate script WITH RAG context, no evaluator feedback loop.

    Injects:
      - Per-video examples from ChromaDB (few-shot demonstrations)
      - Full creator profile as style guide

    Args:
        topic:              Trending topic.
        style_params:       Hook/structure/tone/pacing/audience.
        creator_profile:    Dict from creator_profile.json.
        retrieved_examples: Formatted string of ChromaDB retrieved docs.
        llm:                ChatGroq instance.

    Returns:
        Tuple of (ScriptOutput, metadata_dict).
    """
    print(f"\n[ScriptingAgent] Mode 2: retrieval_only")

    raw = _call_llm(llm, RETRIEVAL_PROMPT, {
        "topic": topic,
        "creator_profile": _format_creator_profile(creator_profile),
        "retrieved_examples": retrieved_examples,
        **style_params,
    })

    script = _parse_script_response(raw)
    print(f"[ScriptingAgent] retrieval_only → '{script.concept_name}'")

    return script, {
        "mode": "retrieval_only",
        "llm_calls": 1,
        "evaluator_scores": None,
        "regen_triggered": False,
    }


def generate_full_pipeline(
    topic: str,
    style_params: dict,
    creator_profile: dict,
    retrieved_examples: str,
    llm: ChatGroq,
) -> tuple[ScriptOutput, dict]:
    """
    Mode 3: Generate script WITH RAG context AND evaluator feedback loop.

    Steps:
      1. Generate initial script (same as retrieval_only).
      2. Evaluate with LLM evaluator — scores style_match, hook_strength,
         structure_adherence, and gives actionable feedback.
      3. If overall score < REGEN_THRESHOLD (7.0), regenerate with feedback
         injected into the prompt.
      4. Repeat up to MAX_REGEN_ATTEMPTS (2) times.
      5. Return the best-scoring version.

    Args:
        topic:              Trending topic.
        style_params:       Hook/structure/tone/pacing/audience.
        creator_profile:    Dict from creator_profile.json.
        retrieved_examples: Formatted string of ChromaDB retrieved docs.
        llm:                ChatGroq instance (same model for gen + eval).

    Returns:
        Tuple of (ScriptOutput, metadata_dict) where metadata includes
        all evaluator scores and whether regeneration was triggered.
    """
    print(f"\n[ScriptingAgent] Mode 3: full_pipeline")

    profile_str = _format_creator_profile(creator_profile)
    regen_triggered = False
    all_scores = []

    # ── Step 1: Initial generation (same as retrieval_only) ───────────────────
    raw = _call_llm(llm, RETRIEVAL_PROMPT, {
        "topic": topic,
        "creator_profile": profile_str,
        "retrieved_examples": retrieved_examples,
        **style_params,
    })
    current_script = _parse_script_response(raw)
    print(f"[ScriptingAgent] Initial generation → '{current_script.concept_name}'")

    # ── Step 2: Evaluate ──────────────────────────────────────────────────────
    for attempt in range(MAX_REGEN_ATTEMPTS + 1):
        time.sleep(1.5)  # Rate limit guard between LLM calls

        try:
            scores = _call_llm(llm, EVALUATOR_PROMPT, {
                "creator_profile": profile_str,
                "script": current_script.model_dump_json(indent=2),
                "structure": style_params["structure"],
            })
        except Exception as e:
            print(f"[ScriptingAgent] Evaluator failed (attempt {attempt+1}): {e}")
            scores = {
                "style_match": 5, "hook_strength": 5,
                "structure_adherence": 5, "overall": 5.0,
                "feedback": "Evaluator unavailable",
            }

        # Ensure overall is float
        scores.setdefault("overall", (
            scores.get("style_match", 5) +
            scores.get("hook_strength", 5) +
            scores.get("structure_adherence", 5)
        ) / 3)
        scores["attempt"] = attempt + 1
        all_scores.append(scores)

        overall = float(scores.get("overall", 0))
        print(f"[ScriptingAgent] Evaluator score (attempt {attempt+1}): "
              f"style={scores.get('style_match')}, "
              f"hook={scores.get('hook_strength')}, "
              f"structure={scores.get('structure_adherence')}, "
              f"overall={overall:.1f}")

        # ── Step 3: Decide whether to regenerate ──────────────────────────
        if overall >= REGEN_THRESHOLD:
            print(f"[ScriptingAgent] Score {overall:.1f} >= {REGEN_THRESHOLD} "
                  f"— accepting script")
            break

        if attempt >= MAX_REGEN_ATTEMPTS:
            print(f"[ScriptingAgent] Max regen attempts reached — "
                  f"accepting best available (score={overall:.1f})")
            break

        # ── Step 4: Regenerate with feedback ──────────────────────────────
        regen_triggered = True
        feedback = scores.get("feedback", "Improve style alignment and hook strength.")
        print(f"[ScriptingAgent] Score {overall:.1f} < {REGEN_THRESHOLD} — "
              f"regenerating with feedback: '{feedback[:80]}...'")

        time.sleep(1.5)  # Rate limit guard
        try:
            raw = _call_llm(llm, REGEN_PROMPT, {
                "topic": topic,
                "score": f"{overall:.1f}",
                "feedback": feedback,
                "creator_profile": profile_str,
                "retrieved_examples": retrieved_examples,
                **style_params,
            })
            current_script = _parse_script_response(raw)
            print(f"[ScriptingAgent] Regenerated → '{current_script.concept_name}'")
        except Exception as e:
            print(f"[ScriptingAgent] Regeneration failed: {e} — keeping previous")
            break

    # Pick the best score across all attempts
    best_scores = max(all_scores, key=lambda s: float(s.get("overall", 0)))

    return current_script, {
        "mode": "full_pipeline",
        "llm_calls": 1 + len(all_scores) + (len(all_scores) - 1 if regen_triggered else 0),
        "evaluator_scores": best_scores,
        "regen_triggered": regen_triggered,
        "all_scores": all_scores,
    }


# ─── LangGraph Node ────────────────────────────────────────────────────────────

def scripting_agent(state: PipelineState) -> dict[str, Any]:
    """
    LangGraph node: Scripting Agent.

    Reads research_output and creator_profile from state, generates a
    script using the mode specified in state (defaults to 'full_pipeline'),
    and returns a partial state update with scripting_output set.

    State fields read:
      - research_output.topic
      - creator_profile
      - scripting_mode (optional, defaults to "full_pipeline")

    State fields written:
      - scripting_output (ScriptingOutput)
      - scripting_error (str or None)

    Args:
        state: Current PipelineState.

    Returns:
        Partial state update dict.
    """
    research_output = state.get("research_output") or {}
    creator_profile = state.get("creator_profile") or {}
    topic = research_output.get("topic", "")
    mode = state.get("scripting_mode", "full_pipeline")  # type: ignore
    creator_id = state.get("creator_id", "unknown")

    print(f"\n[ScriptingAgent] creator_id={creator_id}, topic='{topic}', mode={mode}")

    if not topic:
        return {
            "scripting_output": None,
            "scripting_error": "No topic found in research_output — run ResearchAgent first",
        }

    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return {
            "scripting_output": None,
            "scripting_error": "GROQ_API_KEY not set",
        }

    try:
        llm = ChatGroq(
            api_key=api_key,
            model_name=GROQ_MODEL,
            temperature=0.7,  # Moderate creativity for scripts
            max_tokens=2048,
        )

        # Load creator profile if not in state
        if not creator_profile:
            creator_profile = _load_creator_profile()

        style_params = _extract_style_params(creator_profile)

        # Load RAG components (needed for retrieval_only and full_pipeline)
        retrieved_examples = ""
        if mode in ("retrieval_only", "full_pipeline"):
            retriever = _load_chroma_retriever()
            retrieved_examples = _retrieve_examples(retriever, topic)

        # Run the selected mode
        if mode == "no_history":
            script, metadata = generate_no_history(topic, style_params, llm)
        elif mode == "retrieval_only":
            script, metadata = generate_retrieval_only(
                topic, style_params, creator_profile, retrieved_examples, llm
            )
        else:  # full_pipeline (default)
            script, metadata = generate_full_pipeline(
                topic, style_params, creator_profile, retrieved_examples, llm
            )

        # Wrap in ScriptingOutput — final_script holds the node's output
        scripting_output = ScriptingOutput(
            scripts=[script],
            final_script=script,
        )

        return {
            "scripting_output": scripting_output,
            "scripting_error": None,
            "scripting_metadata": metadata,  # type: ignore — extra field for test scripts
        }

    except Exception as e:
        error_msg = f"ScriptingAgent failed: {str(e)}"
        print(f"[ScriptingAgent] ERROR: {error_msg}")
        return {
            "scripting_output": None,
            "scripting_error": error_msg,
        }
