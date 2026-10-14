"""
scripting_agent.py — LangGraph Scripting Agent Node
=====================================================
Writes 30-second short-form scripts in the creator's own voice, then
checks them with MEASURED metrics and rewrites with concrete feedback.

Flow:
  [1] Context     creator profile (Module 1) + the creator's REAL transcripts
                  (ChromaDB metadata) + speech rate / visual style (Module 2
                  Qdrant snapshot) → style baseline + word budget
                  (30 s × creator's words-per-minute).
  [2] Retrieve    MiniLM: topic → 2-3 most similar past transcripts, shown to
                  the LLM as "this is how this creator talks".
  [3] Generate    LLM (local Ollama by default) in JSON mode → 5 scenes.
                  Pydantic-validated; one repair retry if unusable.
  [4] Evaluate    style_match   stylometrics vs the creator's transcripts
                                (sentence length, "you"-address, questions)
                  timing        spoken words vs the 30-second word budget
                  structure     5 scenes, ordered timecodes, ends ~0:30,
                                real hook, short captions, no near-empty scenes,
                                no repeated scenes, no 8-word runs copied
                                from the creator's past transcripts
                  hook_strength LLM judge, fixed 6-question × 5-level rubric —
                                the ONLY subjective metric. Calibrated once
                                against a deliberately weak control hook; a
                                judge that rates it ≥ 5 is ignored (n/a).
                  overall = mean of the available metrics (0-10).
  [5] Regenerate  full_pipeline only: if overall < 7, any metric < 5, or the script copies /
                  repeats content, rewrite with the measured problems as
                  feedback (max 2 rewrites); keep the best original script.

Three modes (ablation study — FYP research contribution):
  no_history      topic + trend context + hook/structure only
  retrieval_only  + creator profile, word budget, real transcripts
  full_pipeline   retrieval_only + evaluate → regenerate loop
All three get the same trend context, hook type and structure, and ALL
three are scored by the same evaluator, so their scores are comparable.

Product use (server, LangGraph node): generate_variants() runs the full
pipeline once per creator signature hook → 3 distinct variants.
"""

from __future__ import annotations

import json
import os
import re
import statistics
import sys
from pathlib import Path
from typing import Any

import numpy as np
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent.parent

# Load .env
load_dotenv(ROOT / "module1_style_extraction" / ".env")
load_dotenv(ROOT / ".env")

sys.path.insert(0, str(ROOT))
from pipeline.state import PipelineState, ScriptingOutput, ScriptOutput, SceneOutput  # noqa: E402
from pipeline.local_llm import LocalLLMError, chat_json  # noqa: E402
from pipeline.embeddings import embed_texts  # noqa: E402

# ─── Configuration ─────────────────────────────────────────────────────────────
CHROMA_PERSIST_DIR = ROOT / "module1_style_extraction" / "chroma_db"
COLLECTION_NAME = "video_profiles"
CREATOR_PROFILE_PATH = ROOT / "module1_style_extraction" / "creator_profile.json"
QDRANT_SNAPSHOT_PATH = ROOT / "module2_multimodal_rag" / "qdrant_snapshot.json"

MODES = ("no_history", "retrieval_only", "full_pipeline")
DEFAULT_HOOKS = ["Bold Claim", "Curiosity Gap", "Contrarian"]

SCRIPT_DURATION_S = 30
SCENE_COUNT = 5
DEFAULT_WPM = 150            # used only when Module 2 has no speech-rate data
MIN_HOOK_WORDS = 4           # a one-word "hook" (e.g. echoing "Contrarian") is not a hook
MIN_SCENE_WORDS = 3          # same for any scene
COPY_NGRAM = 8               # this many consecutive words from a past transcript = copied
REPEAT_SIMILARITY = 0.8      # word overlap (Jaccard) at which two scenes count as repeats
MAX_HOOK_WORDS = 15
MAX_CAPTION_WORDS = 8

# What each hook type means — small models otherwise write the label itself.
# No quotable example sentences: small models copy them word for word.
HOOK_GUIDE = {
    "contrarian": "say that a popular belief about this topic is wrong, then hint at the real answer",
    "bold claim": "open with a strong, confident statement that sounds surprising",
    "curiosity gap": "tease something the viewer only learns by watching to the end",
    "question": "ask the viewer a direct question they want answered",
    "story": "start in the middle of a short personal moment",
    "shock": "open with a surprising fact or consequence",
    "statistic": "open with one striking number about the topic",
}

RAG_TOP_K = 3
STYLE_LANGUAGE = "en"        # only transcripts spoken in this language define the style
MIN_TRANSCRIPT_WORDS = 20    # shorter transcripts (e.g. a 3-word music video) show no style
MIN_BASELINE_WORDS = 150     # fewer words in total → style_match is low confidence
EXAMPLE_MAX_CHARS = 900      # per transcript in the prompt (small-model context)

GEN_TEMPERATURE = 0.7
GEN_MAX_TOKENS = 1200
REGEN_THRESHOLD = 7.0        # full_pipeline rewrites below this overall score
MIN_METRIC_SCORE = 5.0       # ...or when any single measured metric is below this
MAX_REGEN_ATTEMPTS = 2
STYLE_FEEDBACK_BELOW = 0.7   # per-feature closeness that triggers feedback

METRICS = ("style_match", "timing", "structure", "hook_strength")
YOU_WORDS = {"you", "your", "you're", "youre", "yours", "yourself", "yourselves"}


# ─── [1] Creator Context ───────────────────────────────────────────────────────

def _load_creator_profile() -> dict:
    """Load creator_profile.json from Module 1 ({} if missing)."""
    if not CREATOR_PROFILE_PATH.exists():
        return {}
    with open(CREATOR_PROFILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _json_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value or "[]")
        return parsed if isinstance(parsed, list) else []
    except (TypeError, ValueError):
        return []


def load_creator_examples() -> list[dict]:
    """
    Past videos with their real transcripts from Module 1's ChromaDB.
    Returns [] if ChromaDB is missing or was built before transcripts
    were stored (re-run Module 1 to fix).
    """
    if not CHROMA_PERSIST_DIR.exists():
        print(f"[ScriptingAgent] ChromaDB not found at {CHROMA_PERSIST_DIR} — run Module 1")
        return []
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(CHROMA_PERSIST_DIR))
        metadatas = client.get_collection(COLLECTION_NAME).get(include=["metadatas"])["metadatas"]
    except Exception as e:
        print(f"[ScriptingAgent] ChromaDB read failed: {e}")
        return []

    examples = []
    for meta in metadatas or []:
        transcript = (meta or {}).get("transcript", "")
        if transcript and transcript.strip():
            examples.append({
                "topic": meta.get("topic", ""),
                "hook_type": meta.get("hook_type", ""),
                "hook_text": meta.get("hook_text", ""),
                "key_phrases": _json_list(meta.get("key_phrases")),
                "transcript": transcript.strip(),
                "language": (meta.get("language") or "").lower(),   # Whisper-detected; "" if unknown
            })
    if metadatas and not examples:
        print("[ScriptingAgent] ChromaDB has no transcripts — re-run Module 1 to store them")
    return examples


def load_multimodal_stats() -> dict:
    """Median speech rate and visual style across Module 2's analysed videos."""
    if not QDRANT_SNAPSHOT_PATH.exists():
        return {}
    try:
        with open(QDRANT_SNAPSHOT_PATH, "r", encoding="utf-8") as f:
            payloads = [p.get("payload") or {} for p in json.load(f).get("points", [])]
    except (OSError, ValueError):
        return {}

    def median_of(key: str) -> float | None:
        values = []
        for p in payloads:
            try:
                values.append(float(p[key]))
            except (KeyError, TypeError, ValueError):
                continue
        return statistics.median(values) if values else None

    return {key: median_of(key)
            for key in ("speech_rate_wpm", "talking_head_pct", "avg_shot_duration")}


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", text)


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if _words(s)]


def style_features(text: str) -> dict:
    """Measurable voice markers: sentence length, 'you'-address, questions."""
    words = _words(text)
    sentences = _sentences(text)
    n_words, n_sentences = max(len(words), 1), max(len(sentences), 1)
    return {
        "avg_sentence_words": len(words) / n_sentences,
        "you_ratio": sum(w.lower() in YOU_WORDS for w in words) / n_words,
        "question_ratio": sum(s.rstrip().endswith("?") for s in sentences) / n_sentences,
    }


def build_style_baseline(examples: list[dict], multimodal: dict) -> dict:
    """What the creator sounds like, measured from their transcripts."""
    wpm = multimodal.get("speech_rate_wpm")
    baseline = {
        "wpm": round(wpm or DEFAULT_WPM),
        "wpm_source": "module2_audio" if wpm else "default",
        "word_budget": round((wpm or DEFAULT_WPM) * SCRIPT_DURATION_S / 60),
        "talking_head_pct": multimodal.get("talking_head_pct"),
        "avg_shot_duration": multimodal.get("avg_shot_duration"),
        "measured_style": bool(examples),
        "transcripts": len(examples),
        "baseline_words": sum(len(_words(e["transcript"])) for e in examples),
    }
    baseline["low_confidence"] = baseline["baseline_words"] < MIN_BASELINE_WORDS
    if examples:
        baseline.update(style_features(" ".join(e["transcript"] for e in examples)))
    return baseline


def usable_for_style(example: dict) -> bool:
    """
    A transcript represents the creator's own phrasing only if it was spoken
    in English (Whisper's translation of e.g. a Hindi vlog is machine wording)
    and is long enough to show sentence patterns. Unknown language (ChromaDB
    built before languages were stored) is kept.
    """
    language = example.get("language", "")
    return (len(_words(example["transcript"])) >= MIN_TRANSCRIPT_WORDS
            and (not language or language == STYLE_LANGUAGE))


def prepare_context(profile: dict | None = None) -> dict:
    """Load everything the scripting modes need, once per request."""
    profile = profile or _load_creator_profile()
    all_examples = load_creator_examples()
    examples = [e for e in all_examples if usable_for_style(e)]
    baseline = build_style_baseline(examples, load_multimodal_stats())
    baseline["transcripts_excluded"] = len(all_examples) - len(examples)
    print(f"[ScriptingAgent] Context: {len(examples)} usable transcripts "
          f"({baseline['transcripts_excluded']} excluded: non-English or too short), "
          f"{baseline['baseline_words']} words{' — LOW CONFIDENCE' if baseline['low_confidence'] else ''}, "
          f"{baseline['wpm']} wpm ({baseline['wpm_source']}), budget {baseline['word_budget']} words")
    return {"profile": profile, "examples": examples, "baseline": baseline}


# ─── [2] Retrieval ─────────────────────────────────────────────────────────────

def retrieve_examples(examples: list[dict], topic: str, k: int = RAG_TOP_K) -> list[dict]:
    """Top-k past transcripts most similar to the topic (MiniLM cosine)."""
    if len(examples) <= k:
        return examples
    vectors = embed_texts([f"{e['topic']}. {e['transcript'][:500]}" for e in examples])
    query = embed_texts([topic])[0]
    order = np.argsort(-(vectors @ query))[:k]
    return [examples[i] for i in order]


# ─── [3] Prompting + Generation ────────────────────────────────────────────────

def _format_creator_profile(profile: dict) -> str:
    """Format the creator profile dict as a readable string for prompt injection."""
    if not profile:
        return "No creator profile available."
    fields = [
        ("Niche", profile.get("creator_niche")),
        ("Tone", profile.get("dominant_tone")),
        ("Pacing", profile.get("avg_pacing")),
        ("Typical structure", profile.get("typical_structure")),
        ("Target audience", profile.get("target_audience")),
        ("Signature hooks", ", ".join(profile.get("signature_hooks", []))),
        ("Recurring topics", ", ".join(profile.get("recurring_topics", [])[:5])),
        ("Style summary", profile.get("content_style_summary")),
    ]
    return "\n".join(f"{name}: {value}" for name, value in fields if value)


def _extract_style_params(creator_profile: dict) -> dict:
    """
    Key style parameters shared by all modes, so the ablation compares
    like with like (same hook type and structure in every mode).
    """
    hooks = known_hooks(creator_profile.get("signature_hooks", []))
    return {
        "hook_type": hooks[0] if hooks else "Bold Claim",
        "structure": creator_profile.get("typical_structure", "Hook → Problem → Solution"),
        "tone": creator_profile.get("dominant_tone", "Conversational"),
        "pacing": creator_profile.get("avg_pacing", "Fast-paced"),
        "target_audience": creator_profile.get("target_audience", "General audience"),
    }


def _trend_context(trend: dict | None) -> str:
    if not trend:
        return ""
    lines = []
    if trend.get("why_trending"):
        lines.append(f"Why it is trending: {trend['why_trending']}")
    if trend.get("suggested_angle"):
        lines.append(f"Suggested angle (advice for you as the writer — never say it on camera): "
                     f"{trend['suggested_angle']}")
    # Evidence video titles are deliberately left out: small models copy them
    # (hashtags and emoji included) instead of writing new lines.
    return "TREND CONTEXT:\n" + "\n".join(lines) + "\n\n" if lines else ""


def _hook_instruction(hook_type: str) -> str:
    guide = HOOK_GUIDE.get(hook_type.lower())
    how = f" ({guide})" if guide else ""
    return (f"HOOK: scene 1 is a {hook_type} hook{how}. Write the actual opening sentence — "
            f"do not write the words '{hook_type}' or 'hook'.\n")


def _style_targets(baseline: dict) -> str:
    """
    The creator's measured voice as explicit targets. Examples alone do not
    transfer sentence length (measured in the ablation), numbers do.
    """
    you = baseline["you_ratio"]
    questions = baseline["question_ratio"]
    address = ("talks straight to the viewer ('you', 'your') a lot" if you >= 0.05 else
               "sometimes addresses the viewer as 'you'" if you >= 0.02 else
               "rarely says 'you'")
    asks = ("asks the viewer questions often" if questions >= 0.2 else
            "asks an occasional question" if questions >= 0.05 else
            "almost never asks questions (outside the hook)")
    return (f"VOICE TARGETS (measured from this creator's videos): sentences average "
            f"~{baseline['avg_sentence_words']:.0f} words — keep yours that short; "
            f"this creator {address}, and {asks}.")


def _creator_context(profile: dict, baseline: dict, examples: list[dict]) -> str:
    parts = [f"CREATOR PROFILE:\n{_format_creator_profile(profile)}",
             f"LENGTH: about {baseline['word_budget']} spoken words in total "
             f"(this creator speaks ~{baseline['wpm']} words per minute; 30 seconds)."]
    if baseline.get("measured_style"):
        parts.append(_style_targets(baseline))
    if baseline.get("talking_head_pct") is not None:
        shot = baseline.get("avg_shot_duration")
        parts.append(f"VISUAL STYLE: {baseline['talking_head_pct']:.0%} talking head"
                     + (f", cuts every ~{shot:.1f} s" if shot else "")
                     + " — write clip_ideas to match.")
    if examples:
        shots = "\n\n".join(
            f"--- Example {i} (topic: {e['topic']}) ---\n{e['transcript'][:EXAMPLE_MAX_CHARS]}"
            for i, e in enumerate(examples, 1))
        parts.append("HOW THIS CREATOR ACTUALLY TALKS (real transcripts — copy the voice: "
                     f"sentence length, phrasing, energy; NOT the content):\n{shots}")
    return "\n\n".join(parts) + "\n\n"


# Fixed scene timing (seconds). Small models follow a filled-in skeleton far
# better than a list of rules, so the prompt hands them these slots.
SCENE_SLOTS = [(0, 3, "hook"), (3, 9, "setup"), (9, 16, "main point"),
               (16, 23, "example or proof"), (23, 30, "takeaway")]


def _output_spec(wpm: int) -> str:
    """JSON skeleton with fixed timecodes and per-scene word targets."""
    scenes = []
    for start, end, role in SCENE_SLOTS:
        words = max(4, round((end - start) * wpm / 60))
        if role == "hook":
            words = min(words, MAX_HOOK_WORDS)
        scenes.append(
            f'    {{"timecode": "0:{start:02d}-0:{end:02d}", "clip_idea": "...", '
            f'"caption": "...", "voiceover": "..."}}   <- {role}: about {words} spoken words')
    return (
        f"Fill in this JSON skeleton. Keep all {SCENE_COUNT} scenes and their timecodes exactly; "
        "replace every ... with real content.\n"
        '{"concept_name": "...", "scenes": [\n' + ",\n".join(scenes) + "\n]}\n"
        f"caption = on-screen text, at most {MAX_CAPTION_WORDS} words. "
        "clip_idea = what the viewer sees. voiceover = the exact spoken words.\n"
        "Return only the JSON (without the <- notes)."
    )


def build_prompt(mode: str, topic: str, hook_type: str, structure: str, profile: dict,
                 baseline: dict, examples: list[dict], trend: dict | None = None,
                 feedback: list[str] | None = None, previous: ScriptOutput | None = None) -> str:
    """Prompt for one generation. Only non-baseline modes see creator context."""
    prompt = (
        "You write 30-second short-form video scripts (YouTube Shorts / Reels).\n\n"
        f"TOPIC: {topic}\n"
        + _hook_instruction(hook_type)
        + f"STRUCTURE: {structure}\n\n"
        + _trend_context(trend)
    )
    if mode != "no_history":
        prompt += _creator_context(profile, baseline, examples)
    if feedback and previous is not None:
        draft = "\n".join(f"{s.timecode}: {s.voiceover}" for s in previous.scenes)
        prompt += ("YOUR PREVIOUS DRAFT:\n" + draft + "\n\n"
                   "FIX THESE MEASURED PROBLEMS (keep what already works):\n"
                   + "\n".join(f"- {f}" for f in feedback) + "\n\n")
    # The baseline mode only knows "30 seconds" (generic speech rate); the
    # other modes get the creator's measured words-per-minute.
    return prompt + _output_spec(DEFAULT_WPM if mode == "no_history" else baseline["wpm"])


def _clean_spoken(text: str) -> str:
    """Hashtags and emoji can't be spoken — remove them from a voiceover."""
    text = re.sub(r"#\w+", " ", text)
    text = re.sub(r"[^\w\s'’,.!?;:\-–—…\"]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_script_response(raw: dict, script_id: int = 1, hook_type: str | None = None) -> ScriptOutput:
    """
    Parse and validate the LLM's JSON into a ScriptOutput. Missing fields get
    defaults; hashtags/emoji are stripped from the spoken voiceover; scenes
    with no spoken words (truncation or an echoed "...") are dropped.
    """
    scenes = []
    for i, scene in enumerate(raw.get("scenes") or [], start=1):
        if not isinstance(scene, dict):
            continue
        voiceover = _clean_spoken(str(scene.get("voiceover") or ""))
        if not _words(voiceover):
            continue
        scenes.append(SceneOutput(
            timecode=str(scene.get("timecode") or f"0:{(i - 1) * 6:02d}-0:{i * 6:02d}"),
            clip_idea=str(scene.get("clip_idea") or "Visual placeholder"),
            caption=str(scene.get("caption") or "").strip(),
            voiceover=voiceover,
        ))
    return ScriptOutput(
        script_id=script_id,
        concept_name=str(raw.get("concept_name") or "Untitled Script"),
        hook_type=hook_type or str(raw.get("hook_type") or "Bold Claim"),
        scenes=scenes,
    )


def _script_model() -> str | None:
    """Optional bigger model for scripting (must belong to LLM_PROVIDER)."""
    return os.getenv("SCRIPT_MODEL") or None


def generate_script(prompt: str, script_id: int, hook_type: str) -> ScriptOutput:
    """
    One LLM generation with a single repair retry if the output is unusable.

    Raises:
        LocalLLMError: LLM unreachable, or two unusable answers in a row.
    """
    problem = ""
    for attempt in range(2):
        text = prompt if attempt == 0 else (
            f"{prompt}\n\nYour previous answer was unusable ({problem}). "
            f"Return valid JSON with exactly {SCENE_COUNT} scenes.")
        raw = chat_json(text, temperature=GEN_TEMPERATURE, max_tokens=GEN_MAX_TOKENS,
                        model=_script_model())
        script = _parse_script_response(raw, script_id, hook_type)
        if len(script.scenes) >= 3:
            return script
        problem = f"only {len(script.scenes)} scenes with a voiceover"
    raise LocalLLMError(f"Script generation failed twice: {problem}")


# ─── [4] Evaluation ────────────────────────────────────────────────────────────

def _closeness(value: float, target: float, tolerance: float) -> float:
    """1.0 at target, falling linearly to 0.0 at ±tolerance."""
    return max(0.0, 1.0 - abs(value - target) / tolerance) if tolerance > 0 else float(value == target)


def score_style(text: str, baseline: dict) -> tuple[float | None, list[str], dict]:
    """
    Stylometric match vs the creator's real transcripts. None when there are
    no transcripts to compare against (reported, never guessed).
    """
    features = style_features(text)
    if not baseline.get("measured_style"):
        return None, [], features

    b_len, b_you, b_q = (baseline["avg_sentence_words"], baseline["you_ratio"],
                         baseline["question_ratio"])
    closeness = {
        "length": _closeness(features["avg_sentence_words"], b_len, b_len),
        "you": _closeness(features["you_ratio"], b_you, max(b_you, 0.03)),
        "questions": _closeness(features["question_ratio"], b_q, max(b_q, 0.15)),
    }
    feedback = []
    if closeness["length"] < STYLE_FEEDBACK_BELOW:
        direction = "shorter" if features["avg_sentence_words"] > b_len else "longer"
        feedback.append(f"Average sentence is {features['avg_sentence_words']:.0f} words; this creator "
                        f"averages {b_len:.0f}. Use {direction} sentences.")
    if closeness["you"] < STYLE_FEEDBACK_BELOW:
        feedback.append(f"'You'-words are {features['you_ratio']:.0%} of the script vs {b_you:.0%} "
                        "in the creator's videos. Match how directly they address the viewer.")
    if closeness["questions"] < STYLE_FEEDBACK_BELOW:
        feedback.append(f"{features['question_ratio']:.0%} of sentences are questions vs {b_q:.0%} "
                        "for this creator.")
    return round(10 * statistics.mean(closeness.values()), 1), feedback, features


def score_timing(word_count: int, budget: int, wpm: int) -> tuple[float, list[str]]:
    """Full marks within ±15% of the word budget, 0 at ±60%."""
    deviation = abs(word_count / max(budget, 1) - 1)
    score = 10.0 if deviation <= 0.15 else max(0.0, 10 * (1 - (deviation - 0.15) / 0.45))
    feedback = []
    if deviation > 0.15:
        verb, diff = ("Cut", word_count - budget) if word_count > budget else ("Add", budget - word_count)
        feedback.append(f"Voiceover is {word_count} words; at {wpm} words/min 30 seconds is about "
                        f"{budget}. {verb} about {diff} words.")
    return round(score, 1), feedback


def _parse_timecode(timecode: str) -> tuple[int, int] | None:
    match = re.search(r"(\d+):(\d{1,2})\s*[-–—]\s*(\d+):(\d{1,2})", timecode)
    if not match:
        return None
    m1, s1, m2, s2 = (int(g) for g in match.groups())
    return m1 * 60 + s1, m2 * 60 + s2


def _ngrams(words: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def copied_phrases(text: str, transcripts: list[str]) -> list[str]:
    """COPY_NGRAM-word runs of `text` that appear verbatim in a past transcript."""
    source: set[tuple[str, ...]] = set()
    for t in transcripts:
        source |= _ngrams([w.lower() for w in _words(t)], COPY_NGRAM)
    words = [w.lower() for w in _words(text)]
    return [" ".join(words[i:i + COPY_NGRAM]) for i in range(len(words) - COPY_NGRAM + 1)
            if tuple(words[i:i + COPY_NGRAM]) in source]


def repeated_scenes(scenes: list[SceneOutput]) -> list[int]:
    """1-based numbers of scenes that mostly repeat an earlier scene."""
    word_sets = [{w.lower() for w in _words(s.voiceover)} for s in scenes]
    repeats = []
    for j in range(1, len(word_sets)):
        for i in range(j):
            union = word_sets[i] | word_sets[j]
            if union and len(word_sets[i] & word_sets[j]) / len(union) >= REPEAT_SIMILARITY:
                repeats.append(j + 1)
                break
    return repeats


def score_structure(script: ScriptOutput, transcripts: list[str] | None = None) -> tuple[float, list[str]]:
    """
    Eight pass/fail checks → 0-10: format (scenes, timecodes, length of hook,
    captions, scenes) plus originality — no scene repeating another and no
    word-for-word copying from the creator's past transcripts (small models
    otherwise paste the few-shot examples).
    """
    scenes = script.scenes
    spans = [_parse_timecode(s.timecode) for s in scenes]
    hook_words = len(_words(scenes[0].voiceover)) if scenes else 0
    long_captions = [s.caption for s in scenes if len(_words(s.caption)) > MAX_CAPTION_WORDS]
    thin_scenes = [i for i, s in enumerate(scenes, 1) if len(_words(s.voiceover)) < MIN_SCENE_WORDS]
    ordered = (bool(spans) and all(spans)
               and all(start < end for start, end in spans)
               and all(a[0] <= b[0] for a, b in zip(spans, spans[1:])))
    ends_at = spans[-1][1] if spans and spans[-1] else 0
    repeats = repeated_scenes(scenes)
    copied = copied_phrases(" ".join(s.voiceover for s in scenes), transcripts or [])

    checks = [
        (len(scenes) == SCENE_COUNT, f"Use exactly {SCENE_COUNT} scenes (got {len(scenes)})."),
        (ordered, "Timecodes must be valid (m:ss-m:ss) and in order."),
        (abs(ends_at - SCRIPT_DURATION_S) <= 5, f"Last scene should end near 0:30 (ends at {ends_at} s)."),
        (MIN_HOOK_WORDS <= hook_words <= MAX_HOOK_WORDS,
         f"Hook (scene 1) is {hook_words} words; write a full opening sentence of "
         f"{MIN_HOOK_WORDS}-{MAX_HOOK_WORDS} words."),
        (not long_captions, f"Captions must be {MAX_CAPTION_WORDS} words or fewer "
                            f"({len(long_captions)} are longer)."),
        (not thin_scenes, f"Scenes {', '.join(map(str, thin_scenes))} have under {MIN_SCENE_WORDS} spoken "
                          "words; every scene needs a real spoken sentence."),
        (not repeats, f"Scenes {', '.join(map(str, repeats))} repeat an earlier scene; "
                      "every scene must say something new."),
        (not copied, f"The script copies the creator's past videos word for word "
                     f"(e.g. '{copied[0] if copied else ''}'). Write new lines in their style."),
    ]
    passed = sum(ok for ok, _ in checks)
    return round(10 * passed / len(checks), 1), [msg for ok, msg in checks if not ok]


# 5-level answers: finer than yes/partly/no, which scored every decent hook 8.8.
_RUBRIC_VALUE = {"yes": 1.0, "mostly": 0.75, "partly": 0.5, "slightly": 0.25, "no": 0.0}
_RUBRIC_QUESTIONS = [
    "Would a viewer feel they must keep watching (open loop, tension or surprise)?",
    "Is it specific to this topic, not a line that could open any video?",
    "Does it contain a concrete detail (a number, a named thing, a vivid image or a personal moment)?",
    "Does it promise the viewer a clear benefit or answer?",
    "Is it clearly a '{hook_type}' hook?",
    "Can it be said in about 3 seconds and understood on first hearing?",
]


def _ask_judge(hook: str, hook_type: str, topic: str) -> tuple[float, str]:
    """
    One rubric call: 6 questions answered on a 5-level scale → 0-10, plus an
    improvement tip. Validated on graded example hooks (bad / generic / strong):
    means 1.1 / 2.8 / 9.2, vs 1.7 / 4.6 / 9.2 for the earlier 4×3 rubric.

    Raises:
        LocalLLMError: judge unreachable or answers not in the rubric.
    """
    keys = [f"q{i}" for i in range(1, len(_RUBRIC_QUESTIONS) + 1)]
    questions = "\n".join(f"{k}: {q.format(hook_type=hook_type)}" for k, q in zip(keys, _RUBRIC_QUESTIONS))
    prompt = (
        "You judge the opening line (hook) of a 30-second short-form video.\n"
        f"Topic: {topic}\nIntended hook type: {hook_type}\nHook: \"{hook}\"\n\n"
        f"Answer each question with one of: {', '.join(_RUBRIC_VALUE)}.\n{questions}\n"
        "improve: one sentence on how to make this hook stronger.\n"
        "Return JSON: {" + ", ".join(f'"{k}": "..."' for k in keys) + ', "improve": "..."}'
    )
    result = chat_json(prompt, temperature=0.0, max_tokens=400, model=_script_model())
    answers = [_RUBRIC_VALUE.get(str(result.get(k, "")).strip().lower()) for k in keys]
    if any(a is None for a in answers):
        raise LocalLLMError(f"Judge answers outside the rubric: {result}")
    return round(10 * statistics.mean(answers), 1), str(result.get("improve", "")).strip()


# Calibration control: a deliberately weak, generic hook. A judge that rates
# it CONTROL_MAX_SCORE or higher can't tell good from bad, so its scores are
# not used. Checked once per model per process.
CONTROL_HOOK = "This video is about life and some things about it."
CONTROL_MAX_SCORE = 5.0
_judge_reliability: dict[str, bool] = {}


def judge_is_reliable() -> bool:
    key = _script_model() or f"{os.getenv('LLM_PROVIDER', 'ollama')}:{os.getenv('OLLAMA_MODEL', '')}"
    if key not in _judge_reliability:
        try:
            control_score, _ = _ask_judge(CONTROL_HOOK, "Curiosity Gap", "Living a better life")
            reliable = control_score < CONTROL_MAX_SCORE
            print(f"[ScriptingAgent] Hook judge calibration: control hook scored {control_score} → "
                  f"{'reliable' if reliable else 'UNRELIABLE, hook_strength will be n/a'}")
        except LocalLLMError as e:
            print(f"[ScriptingAgent] Hook judge calibration failed: {e}")
            reliable = False
        _judge_reliability[key] = reliable
    return _judge_reliability[key]


def judge_hook(hook: str, hook_type: str, topic: str) -> tuple[float | None, list[str]]:
    """
    LLM judge with a fixed 6-question rubric (5 levels → 0-10) — the
    only subjective metric. None when the judge is unavailable or fails the
    calibration control. A hook shorter than MIN_HOOK_WORDS scores 0 without
    asking: small judge models rate even a single word like "Contrarian" highly.
    """
    if len(_words(hook)) < MIN_HOOK_WORDS:
        return 0.0, [f"Hook: write a real opening sentence, not '{hook}'."]
    if not judge_is_reliable():
        return None, []
    try:
        score, improve = _ask_judge(hook, hook_type, topic)
    except LocalLLMError as e:
        print(f"[ScriptingAgent] Hook judge unavailable: {e}")
        return None, []
    # Small models sometimes echo the placeholder instead of answering
    useful = len(_words(improve)) >= 3 and "one sentence" not in improve.lower()
    return score, ([f"Hook: {improve}"] if useful and score < 10 else [])


def evaluate_script(script: ScriptOutput, baseline: dict, topic: str,
                    transcripts: list[str] | None = None) -> dict:
    """
    Score a script on the four metrics; same evaluator for every mode.
    `transcripts` (the creator's past videos) are used for the copy check.
    """
    voiceover = " ".join(s.voiceover for s in script.scenes)
    word_count = len(_words(voiceover))

    # Style is measured on the body (scenes 2+): the hook's form is set by the
    # requested hook type (a Curiosity Gap is often a question), not by voice.
    body = " ".join(s.voiceover for s in script.scenes[1:]) or voiceover
    style, style_fb, features = score_style(body, baseline)
    timing, timing_fb = score_timing(word_count, baseline["word_budget"], baseline["wpm"])
    structure, structure_fb = score_structure(script, transcripts)
    hook = script.scenes[0].voiceover if script.scenes else ""
    hook_strength, hook_fb = judge_hook(hook, script.hook_type, topic)

    available = [s for s in (style, timing, structure, hook_strength) if s is not None]
    return {
        "style_match": style,
        "timing": timing,
        "structure": structure,
        "hook_strength": hook_strength,
        "overall": round(statistics.mean(available), 2),
        # Copied or repeated content never passes, whatever the overall score
        "original": not (repeated_scenes(script.scenes) or copied_phrases(voiceover, transcripts or [])),
        "feedback": timing_fb + structure_fb + style_fb + hook_fb,
        "measured": {"word_count": word_count, **{k: round(v, 3) for k, v in features.items()}},
    }


# ─── [5] Modes ─────────────────────────────────────────────────────────────────

def run_mode(mode: str, topic: str, context: dict, examples: list[dict], hook_type: str,
             trend: dict | None = None, script_id: int = 1) -> tuple[ScriptOutput, dict]:
    """
    Generate (and for full_pipeline, refine) one script in the given mode.
    Every mode is evaluated, so scores are comparable across modes.

    Raises:
        LocalLLMError: the LLM could not produce a usable script.
    """
    if mode not in MODES:
        raise ValueError(f"Unknown scripting mode: {mode}")
    profile, baseline = context["profile"], context["baseline"]
    structure = _extract_style_params(profile)["structure"]
    shots = examples if mode != "no_history" else []
    transcripts = [e["transcript"] for e in context["examples"]]

    def attempt(feedback=None, previous=None) -> tuple[ScriptOutput, dict]:
        prompt = build_prompt(mode, topic, hook_type, structure, profile, baseline, shots,
                              trend, feedback, previous)
        script = generate_script(prompt, script_id, hook_type)
        return script, evaluate_script(script, baseline, topic, transcripts)

    script, scores = attempt()
    history = [{"attempt": 1, **scores}]
    best_script, best_scores = script, scores

    if mode == "full_pipeline":
        def weakest(s: dict) -> float:
            return min(v for k in METRICS if (v := s[k]) is not None)

        def passes(s: dict) -> bool:
            # a high average must not hide one bad metric (e.g. style 1.8)
            return s["overall"] >= REGEN_THRESHOLD and weakest(s) >= MIN_METRIC_SCORE and s["original"]

        def rank(s: dict) -> tuple:   # an original script always beats a copied one
            return s["original"], s["overall"]

        while not passes(scores) and len(history) <= MAX_REGEN_ATTEMPTS and scores["feedback"]:
            reason = ("copied/repeated content" if not scores["original"] else
                      f"overall {scores['overall']}, weakest metric {weakest(scores)}")
            print(f"[ScriptingAgent] {hook_type}: {reason} — rewriting with {len(scores['feedback'])} fixes")
            script, scores = attempt(scores["feedback"], script)
            history.append({"attempt": len(history) + 1, **scores})
            if rank(scores) > rank(best_scores):
                best_script, best_scores = script, scores

    print(f"[ScriptingAgent] {mode} / {hook_type}: overall {best_scores['overall']} "
          f"after {len(history)} attempt(s)")
    return best_script, {
        "mode": mode,
        "hook_type": hook_type,
        "structure": structure,
        "evaluator_scores": best_scores,
        "all_scores": history,
        "regen_triggered": len(history) > 1,
        "examples_used": len(shots),
        "baseline": {k: v for k, v in baseline.items()
                     if k in ("wpm", "wpm_source", "word_budget", "measured_style", "transcripts",
                              "transcripts_excluded", "baseline_words", "low_confidence")},
    }


def known_hooks(hooks: list) -> list[str]:
    """
    Keep only recognised hook types (HOOK_GUIDE), title-cased. A weak profiling
    model can put garbage in signature_hooks (e.g. a mistranslated phrase) —
    writing a script "in that hook type" makes no sense.
    """
    return [h.strip().title() for h in hooks
            if isinstance(h, str) and h.strip().lower() in HOOK_GUIDE]


def variant_hooks(profile: dict, n: int = 3) -> list[str]:
    """The creator's (recognised) signature hooks first, topped up with common defaults."""
    return list(dict.fromkeys(known_hooks(profile.get("signature_hooks", [])) + DEFAULT_HOOKS))[:n]


def generate_variants(topic: str, trend: dict | None = None, profile: dict | None = None,
                      n: int = 3) -> list[tuple[ScriptOutput, dict]]:
    """
    Product path: full pipeline once per signature hook → n distinct variants.

    Raises:
        LocalLLMError: if every variant failed.
    """
    context = prepare_context(profile)
    examples = retrieve_examples(context["examples"], topic)
    results, errors = [], []
    for i, hook in enumerate(variant_hooks(context["profile"], n), 1):
        try:
            results.append(run_mode("full_pipeline", topic, context, examples, hook, trend, script_id=i))
        except LocalLLMError as e:
            print(f"[ScriptingAgent] Variant '{hook}' failed: {e}")
            errors.append(str(e))
    if not results:
        raise LocalLLMError(f"All script variants failed: {errors[0] if errors else 'unknown error'}")
    return results


def run_ablation(topic: str, trend: dict | None = None, profile: dict | None = None,
                 hook_type: str | None = None) -> dict[str, tuple[ScriptOutput, dict]]:
    """Research path: the same topic/hook through all three modes, same evaluator."""
    context = prepare_context(profile)
    examples = retrieve_examples(context["examples"], topic)
    hook = hook_type or _extract_style_params(context["profile"])["hook_type"]
    return {mode: run_mode(mode, topic, context, examples, hook, trend) for mode in MODES}


# ─── LangGraph Node ────────────────────────────────────────────────────────────

def scripting_agent(state: PipelineState) -> dict[str, Any]:
    """
    LangGraph node: Scripting Agent.

    Reads research_output (topic + trend context) and creator_profile.
    Default: 3 full-pipeline variants (one per signature hook), with the
    highest-scoring one as final_script. If state["scripting_mode"] names
    an ablation mode, only that mode runs.
    """
    research_output = state.get("research_output") or {}
    topic = research_output.get("topic", "")
    mode = state.get("scripting_mode")  # type: ignore[typeddict-item]
    print(f"\n[ScriptingAgent] creator_id={state.get('creator_id', 'unknown')}, "
          f"topic='{topic}', mode={mode or 'variants'}")

    if not topic:
        return {"scripting_output": None,
                "scripting_error": "No topic found in research_output — run ResearchAgent first"}

    try:
        profile = state.get("creator_profile") or None
        if mode in MODES:
            context = prepare_context(profile)
            examples = retrieve_examples(context["examples"], topic)
            hook = _extract_style_params(context["profile"])["hook_type"]
            results = [run_mode(mode, topic, context, examples, hook, research_output)]
        else:
            results = generate_variants(topic, research_output, profile)

        best_script, _ = max(results, key=lambda r: r[1]["evaluator_scores"]["overall"])
        return {
            "scripting_output": ScriptingOutput(scripts=[s for s, _ in results], final_script=best_script),
            "scripting_error": None,
            "scripting_metadata": [m for _, m in results],  # type: ignore — extra field for test scripts
        }
    except (LocalLLMError, ValueError) as e:
        print(f"[ScriptingAgent] ERROR: {e}")
        return {"scripting_output": None, "scripting_error": f"ScriptingAgent failed: {e}"}
