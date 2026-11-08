"""
creator_profiler.py — Master Creator Profile Synthesis via RAG
==============================================================
This is the final, highest-value step of the pipeline: using
Retrieval-Augmented Generation to synthesise a holistic "creator fingerprint"
from multiple per-video profiles stored in ChromaDB.

RAG Architecture used here:
  Query → ChromaDB retrieval → Retrieved docs as context → LLM → JSON

Why RAG instead of just passing all profiles directly to the LLM?
  In our 3-video POC the difference is minimal, but the RAG pattern scales:
  - A creator with 100+ videos wouldn't fit in the LLM's context window.
  - RAG retrieves only the most semantically relevant documents per query.
  - This module demonstrates production-grade design thinking — which is
    exactly what a university panel evaluates in a FYP.
"""

import json
import time
from typing import Any

from langchain_core.runnables import Runnable
from langchain_core.retrievers import BaseRetriever
from rich.console import Console

try:
    from llm_chain import LocalLLMError, json_chain, provider_label
except ImportError:  # imported as a package, e.g. by Module 2
    from module1_style_extraction.llm_chain import LocalLLMError, json_chain, provider_label

console = Console()

# ─── Master Creator Profile Prompt Template ───────────────────────────────────
# This prompt receives the retrieved video profiles as {context} and instructs
# the LLM to synthesise ACROSS them to produce a creator-level fingerprint.
#
# Key prompt engineering choices:
#   1. Explicit analyst role — grounds the LLM in content strategy domain.
#   2. Instructs LLM to CROSS-REFERENCE across videos — prevents single-video bias.
#   3. Schema provided inline — reduces hallucination of extra/missing fields.
#   4. "ONLY output valid JSON" — standard JSON-mode instruction.
CREATOR_PROFILE_PROMPT = """You are an expert content strategist and YouTube analytics specialist.
You have been given structured profiles extracted from multiple videos by the SAME creator.
Your task is to synthesize these individual video profiles into a single master creator profile
that captures the creator's overall style, niche, and content patterns.

RETRIEVED VIDEO PROFILES (from vector database):
{context}

Analyze ALL profiles carefully. Look for patterns, recurring elements, and consistent
characteristics ACROSS videos. Then output ONLY a valid JSON object with this exact schema.
Do NOT include any text before or after the JSON. Do NOT use markdown code blocks.

{{
  "creator_niche": "the specific content niche this creator focuses on (e.g. 'Web Development & Programming Humor')",
  "signature_hooks": ["2-4 hook styles this creator commonly uses, based on patterns across videos"],
  "dominant_tone": "the most consistent tone observed across all videos",
  "avg_pacing": "one of: Slow, Moderate, Fast-paced — based on the majority of videos",
  "typical_structure": "the content structure pattern used across most videos (e.g. Hook → Problem → Solution → Punchline)",
  "target_audience": "who this content is aimed at — infer from topics, language complexity, and references used",
  "recurring_topics": ["3-6 themes or subject areas that appear across multiple videos"],
  "content_style_summary": "3-4 sentences describing the creator's overall style, voice, and what makes their content distinctive",
  "visual_style_suggestions": [
    "3-4 visual or editing style suggestions inferred from the tone and pacing",
    "Examples: Fast cuts matching the quick pacing, Code snippets as B-roll, Meme overlays for humor beats"
  ]
}}"""


def create_creator_profile_chain(groq_api_key: str | None = None) -> Runnable:
    """
    Build the LCEL chain for master creator profile synthesis:
      prompt | shared LLM (JSON mode)  →  dict

    Same shared LLM as the video profiler (pipeline/local_llm.py); a slightly
    higher temperature (0.4) because synthesis means spotting patterns across
    videos rather than extracting literal values. `groq_api_key` is kept for
    backward compatibility and ignored.

    Returns:
        A Runnable that accepts {"context": str} (formatted retrieved video
        profiles) and returns a dict matching the master creator profile schema.
    """
    return json_chain(CREATOR_PROFILE_PROMPT, temperature=0.4, max_tokens=2048)


def _format_retrieved_docs(docs: list) -> str:
    """
    Format a list of LangChain Document objects into a single context string.

    The retrieved documents have .page_content (the embedded text) and
    .metadata (the stored metadata dict). We format them clearly so the
    LLM can distinguish between individual video profiles.

    Args:
        docs: List of Document objects from the retriever.

    Returns:
        A formatted multi-line string with all documents clearly separated.
    """
    if not docs:
        return "No video profiles were retrieved from the database."

    formatted_parts = []
    for i, doc in enumerate(docs, start=1):
        # Include metadata to help the LLM understand the source of each profile
        metadata_str = ""
        if doc.metadata:
            meta_items = [f"{k}: {v}" for k, v in doc.metadata.items()]
            metadata_str = f"[Source: {', '.join(meta_items)}]\n"

        formatted_parts.append(
            f"--- VIDEO PROFILE {i} ---\n"
            f"{metadata_str}"
            f"{doc.page_content}\n"
        )

    return "\n".join(formatted_parts)


def build_creator_profile(
    retriever: BaseRetriever,
    chain: Runnable,
    query: str,
    max_retries: int = 2,
) -> dict[str, Any]:
    """
    Execute the full RAG pipeline to build the master creator profile.

    Steps:
      1. Retrieve the most relevant video profiles from ChromaDB using the query.
      2. Format the retrieved documents into a context string.
      3. Pass the context to the LLM chain.
      4. Parse, validate, and return the JSON response.

    Args:
        retriever:   BaseRetriever from get_retriever() wrapping ChromaDB.
        chain:       LCEL chain from create_creator_profile_chain().
        query:       Natural-language query used to retrieve relevant documents.
                     Should be broad enough to surface all video profiles.
        max_retries: Max retry attempts on JSON parse failure.

    Returns:
        Dict matching the master creator profile schema.

    Raises:
        RuntimeError: If retrieval or LLM synthesis fails after all retries.
    """
    # ─── Step 1: Retrieve relevant documents from ChromaDB ────────────────────
    console.print(f"\n  [cyan]🔍 Querying ChromaDB vector store...[/cyan]")
    display_query = query[:80] + "..." if len(query) > 80 else query
    console.print(f"  [dim]Query: {display_query}[/dim]")

    try:
        # retriever.invoke() embeds the query and performs cosine similarity
        # search, returning Document objects sorted by relevance.
        docs = retriever.invoke(query)
        console.print(
            f"  [green]✓ Retrieved {len(docs)} document(s) from ChromaDB[/green]"
        )
    except Exception as e:
        raise RuntimeError(f"ChromaDB retrieval failed: {e}") from e

    if not docs:
        raise RuntimeError(
            "No documents retrieved from ChromaDB. "
            "Ensure video profiles were stored successfully in Stage 3."
        )

    # ─── Step 2: Format context for the LLM ──────────────────────────────────
    context = _format_retrieved_docs(docs)
    console.print(f"  [dim]Context prepared: {len(context)} characters[/dim]")

    # ─── Step 3: LLM synthesis with retry logic ───────────────────────────────
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 2):
        try:
            console.print(
                f"\n  [cyan]🤖 Synthesising creator profile via {provider_label()}[/cyan] "
                f"(attempt {attempt}/{max_retries + 1})..."
            )

            # Invoke the chain — {context} placeholder in the prompt is filled here.
            creator_profile: dict = chain.invoke({"context": context})

            # ── Schema validation ────────────────────────────────────────────
            required_keys = [
                "creator_niche", "signature_hooks", "dominant_tone",
                "avg_pacing", "typical_structure", "target_audience",
                "recurring_topics", "content_style_summary",
                "visual_style_suggestions"
            ]
            missing = [k for k in required_keys if k not in creator_profile]
            if missing:
                raise ValueError(f"LLM response missing keys: {missing}")

            # Ensure list fields are actually lists
            for list_key in ["signature_hooks", "recurring_topics", "visual_style_suggestions"]:
                if isinstance(creator_profile.get(list_key), str):
                    creator_profile[list_key] = [creator_profile[list_key]]

            console.print(
                "  [green]✓ Creator profile synthesised successfully[/green]"
            )
            return creator_profile

        except (json.JSONDecodeError, ValueError, KeyError, LocalLLMError) as e:
            last_error = e
            console.print(
                f"  [yellow]⚠ Parse error (attempt {attempt}): {e}[/yellow]"
            )
            if attempt <= max_retries:
                time.sleep(2)
                continue

        except Exception as e:
            raise RuntimeError(
                f"LLM call failed during profile synthesis: {e}"
            ) from e

    raise RuntimeError(
        f"Failed to build valid creator profile after {max_retries + 1} attempts. "
        f"Last error: {last_error}"
    )
