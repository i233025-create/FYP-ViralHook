
"""
video_profiler.py — Per-Video Profile Extraction via LLM
=========================================================
This module takes a raw transcript and uses an LLM to extract a structured
per-video profile: topic, hook, tone, pacing, etc.

Architecture — LCEL (LangChain Expression Language):
  We use the pipe operator pattern:  prompt | llm | output_parser
  This creates a "chain" object that is composable, readable, and testable.
  LCEL is LangChain's modern recommended approach (vs the older LLMChain).

Which LLM?
  The shared client in pipeline/local_llm.py: a local Ollama model by default
  (no API, no key), or Groq when LLM_PROVIDER=groq. See llm_chain.py.
"""

import json
import time
from typing import Any

from langchain_core.runnables import Runnable
from rich.console import Console

try:
    from llm_chain import LocalLLMError, json_chain, provider_label
except ImportError:  # imported as a package, e.g. by Module 2
    from module1_style_extraction.llm_chain import LocalLLMError, json_chain, provider_label

console = Console()

# ─── Per-Video Profile Prompt Template ────────────────────────────────────────
# This is the instruction given to the LLM for EVERY video it processes.
#
# Key prompt engineering decisions:
#   1. Role-setting ("expert content strategist") — guides the model's persona
#      toward content analysis rather than general-purpose QA.
#   2. Explicit JSON schema with field descriptions — reduces hallucination
#      of extra fields or wrong data types.
#   3. "ONLY output valid JSON" — minimises prose wrapper text that would
#      break the JSON parser.
#   4. {transcript} and {video_url} are LCEL placeholders filled at runtime.
VIDEO_PROFILE_PROMPT = """You are an expert content strategist and YouTube analytics specialist.
Your task is to analyze the following YouTube Shorts transcript and extract a structured content profile.

TRANSCRIPT:
{transcript}

VIDEO URL: {video_url}

Analyze the transcript carefully and output ONLY a valid JSON object with this exact schema.
Do NOT include any text before or after the JSON. Do NOT use markdown code blocks.

{{
  "topic": "the main subject or topic of this video in 5-10 words",
  "hook_text": "the exact opening 1-2 sentences used to grab attention",
  "hook_type": "one of: Contrarian, Curiosity Gap, Bold Claim, Question, Statistic, Story",
  "structure": "the narrative structure, e.g. Problem → Solution → Demo or Hook → Explanation → CTA",
  "tone": "one of: Conversational, Technical, Humorous, Inspirational, Sarcastic, Educational",
  "pacing": "one of: Slow, Moderate, Fast-paced",
  "key_phrases": ["3-5 memorable phrases, catchphrases, or distinctive word choices from the transcript"],
  "transcript_summary": "2-3 sentence summary of what the video covers and its main takeaway"
}}"""


def create_video_profiler_chain(groq_api_key: str | None = None) -> Runnable:
    """
    Build the LCEL chain for per-video profile extraction:
      prompt | shared LLM (JSON mode)  →  dict

    The LLM comes from pipeline/local_llm.py (LLM_PROVIDER: local Ollama by
    default, Groq optional). `groq_api_key` is kept for backward
    compatibility and ignored — Groq reads GROQ_API_KEY from the environment.

    temperature=0.3: low, because this is structured extraction — we want
    consistency, with a little randomness so retries can differ.

    Returns:
        A Runnable that accepts {"transcript": str, "video_url": str}
        and returns a dict matching the per-video profile schema.
    """
    return json_chain(VIDEO_PROFILE_PROMPT, temperature=0.3, max_tokens=1024)


def extract_video_profile(
    chain: Runnable,
    transcript: str,
    video_url: str,
    max_retries: int = 2,
) -> dict[str, Any]:
    """
    Run the profiler chain on a transcript and return the structured profile.

    Includes retry logic because LLMs occasionally produce slightly malformed
    JSON (trailing comma, unescaped quote, etc.). On failure we retry with
    the same inputs — the LLM's stochastic nature means a retry often succeeds.

    Args:
        chain:       The LCEL chain from create_video_profiler_chain().
        transcript:  Raw transcript text from Whisper.
        video_url:   The source YouTube URL (added to profile for traceability).
        max_retries: Maximum additional retry attempts on JSON parse failure.

    Returns:
        Dict matching the per-video profile schema, with an extra "video_url"
        key added for traceability in ChromaDB.

    Raises:
        RuntimeError: If JSON parsing fails after all retries are exhausted.
    """
    # Guard against empty transcripts — sending an empty transcript to the
    # LLM would produce meaningless output and waste API quota.
    if not transcript or not transcript.strip():
        console.print(
            "  [yellow]⚠ Empty transcript — returning placeholder profile[/yellow]"
        )
        return {
            "topic": "Unknown (empty transcript)",
            "hook_text": "",
            "hook_type": "Unknown",
            "structure": "Unknown",
            "tone": "Unknown",
            "pacing": "Unknown",
            "key_phrases": [],
            "transcript_summary": "No transcript was available for this video.",
            "video_url": video_url,
        }

    last_error: Exception | None = None

    for attempt in range(1, max_retries + 2):  # +2: range exclusive, start at 1
        try:
            console.print(
                f"  [cyan]🤖 Sending to LLM: {provider_label()}[/cyan] "
                f"(attempt {attempt}/{max_retries + 1})..."
            )

            # chain.invoke() sends the formatted prompt to the LLM and returns
            # the parsed JSON dict (JSON mode in pipeline/local_llm.py).
            profile: dict = chain.invoke({
                "transcript": transcript,
                "video_url": video_url,
            })

            # ── Lightweight schema validation ────────────────────────────────
            # Check all expected keys are present. If a key is missing, the
            # downstream ChromaDB storage and RAG steps would fail silently,
            # so we catch it here and trigger a retry instead.
            required_keys = [
                "topic", "hook_text", "hook_type", "structure",
                "tone", "pacing", "key_phrases", "transcript_summary"
            ]
            missing = [k for k in required_keys if k not in profile]
            if missing:
                raise ValueError(f"LLM response missing keys: {missing}")

            # Ensure key_phrases is always a list (LLM sometimes returns string)
            if isinstance(profile.get("key_phrases"), str):
                profile["key_phrases"] = [profile["key_phrases"]]

            # Add source URL for traceability in the vector store
            profile["video_url"] = video_url

            console.print(
                f"  [green]✓ Profile extracted:[/green] "
                f"{profile.get('topic', 'N/A')} | {profile.get('tone', '')} | "
                f"{profile.get('pacing', '')}"
            )
            return profile

        except (json.JSONDecodeError, ValueError, KeyError, LocalLLMError) as e:
            # LocalLLMError: invalid JSON from a small local model is worth a retry
            last_error = e
            console.print(
                f"  [yellow]⚠ JSON parse error (attempt {attempt}): {e}[/yellow]"
            )
            if attempt <= max_retries:
                # Brief wait before retry — avoids hammering the API on
                # consecutive failures and respects rate limits.
                time.sleep(2)
                continue

        except Exception as e:
            # Network errors, auth errors, etc. — not retryable
            raise RuntimeError(f"LLM call failed: {e}") from e

    raise RuntimeError(
        f"Failed to extract valid JSON profile after {max_retries + 1} attempts. "
        f"Last error: {last_error}"
    )
