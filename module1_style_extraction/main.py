"""
main.py — Pipeline Orchestrator for Module 1: RAG-based Style & Niche Extraction
==================================================================================
This is the entry point for the entire pipeline. It wires together all the
individual modules and executes the full workflow end-to-end.

Pipeline Stages:
  ┌─────────────────────────────────────────────────────────────────────┐
  │ STAGE 0: Initialisation                                             │
  │   Load env vars, validate API key, check ffmpeg, create dirs       │
  │                                                                     │
  │ STAGE 1: Transcription (per video)                                  │
  │   yt-dlp downloads audio → Whisper tiny (CPU) transcribes          │
  │                                                                     │
  │ STAGE 2: Profile Extraction (per video)                             │
  │   Transcript → LLM (local Ollama / Groq) → per-video profile JSON  │
  │                                                                     │
  │ STAGE 3: Vector Storage (per video)                                 │
  │   Profile text → all-MiniLM-L6-v2 embedding → ChromaDB             │
  │                                                                     │
  │ STAGE 4: RAG Synthesis (once, after all videos)                     │
  │   Query → ChromaDB retrieval → LLM → creator profile               │
  │                                                                     │
  │ STAGE 5: Output                                                     │
  │   Print JSON to terminal + save to creator_profile.json            │
  └─────────────────────────────────────────────────────────────────────┘

Run with:
  python main.py

Prerequisites:
  - Ollama running locally (default), or LLM_PROVIDER=groq + GROQ_API_KEY in .env
  - ffmpeg installed and on system PATH
  - pip install -r requirements.txt
"""

import json
import os
import sys
import time
from pathlib import Path

import requests

# ─── Rich Terminal Output ─────────────────────────────────────────────────────
# Rich provides beautiful formatted terminal output — important for a live demo
# to a university panel. Panel, Table, Rule are layout components.
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule

# ─── Local Module Imports ─────────────────────────────────────────────────────
from config import (
    GROQ_API_KEY,
    WHISPER_MODEL,
    WHISPER_LANGUAGE,
    WHISPER_TASK,
    CHROMA_PERSIST_DIR,
    COLLECTION_NAME,
    TEMP_AUDIO_DIR,
    OUTPUT_FILE,
    SAMPLE_VIDEO_URLS,
    INPUT_MODE,
    LOCAL_VIDEO_DIR,
    API_CALL_DELAY,
    RAG_TOP_K,
    MAX_JSON_RETRIES,
)
import transcriber
from transcriber import process_video, process_local_video, get_local_videos
from video_profiler import create_video_profiler_chain, extract_video_profile
from vector_store import initialize_vector_store, store_video_profile, get_retriever
from creator_profiler import create_creator_profile_chain, build_creator_profile
from llm_chain import provider_label

console = Console()


def print_banner() -> None:
    """
    Print a styled pipeline banner to the terminal.
    Rich's Panel widget creates a bordered box with coloured text.
    """
    banner_text = (
        "  [green]→[/green] Transcription:  [white]OpenAI Whisper (tiny, local CPU)[/white]\n"
        f"  [green]→[/green] LLM:            [white]{provider_label()}[/white]\n"
        "  [green]→[/green] Embeddings:     [white]all-MiniLM-L6-v2 (HuggingFace, local)[/white]\n"
        "  [green]→[/green] Vector Store:   [white]ChromaDB (local, persistent)[/white]\n"
        "  [green]→[/green] Creator:        [white]Fireship — 3 YouTube Shorts[/white]"
    )
    console.print(Panel(
        banner_text,
        title="[bold cyan]🎬 Module 1: RAG-based Style & Niche Extraction[/bold cyan]",
        subtitle="[dim]Final Year Project — AI Content Creation Pipeline[/dim]",
        border_style="cyan",
    ))
    console.print()


def validate_configuration() -> None:
    """
    Validate all required configuration before starting the pipeline.

    Failing fast with clear error messages is far better than crashing
    partway through after spending minutes downloading and transcribing videos.

    Raises:
        SystemExit: If any required configuration is missing.
    """
    console.print(Rule("[bold]Pre-flight Configuration Check[/bold]", style="dim"))

    errors = []

    # ── LLM check (shared client: local Ollama by default, Groq optional) ────
    if os.getenv("LLM_PROVIDER", "ollama").lower() == "groq":
        if not GROQ_API_KEY or GROQ_API_KEY == "your_groq_api_key_here":
            errors.append(
                "LLM_PROVIDER=groq but GROQ_API_KEY is not set. "
                "Add it to .env, or use the local LLM (LLM_PROVIDER=ollama)."
            )
        else:
            # Only display first/last 4 characters — never log full API keys
            masked = GROQ_API_KEY[:4] + "..." + GROQ_API_KEY[-4:]
            console.print(f"  [green]✓[/green] LLM: {provider_label()} — key {masked}")
    else:
        host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        try:
            requests.get(f"{host}/api/tags", timeout=3).raise_for_status()
            console.print(f"  [green]✓[/green] LLM: {provider_label()} at {host} (local, no API)")
        except requests.RequestException:
            errors.append(
                f"Ollama is not reachable at {host}. Start Ollama "
                "(https://ollama.com) or set LLM_PROVIDER=groq in .env."
            )

    # ── Video URLs check ─────────────────────────────────────────────────────
    if not SAMPLE_VIDEO_URLS:
        errors.append("SAMPLE_VIDEO_URLS is empty in config.py")
    else:
        console.print(f"  [green]✓[/green] Videos to process: {len(SAMPLE_VIDEO_URLS)}")

    # ── ffmpeg check — yt-dlp requires it for audio conversion ───────────────
    import shutil
    if shutil.which("ffmpeg") is None:
        errors.append(
            "ffmpeg not found on PATH. "
            "Windows: download from https://ffmpeg.org/download.html "
            "and add the bin/ folder to your system PATH."
        )
    else:
        console.print("  [green]✓[/green] ffmpeg found on PATH")

    console.print(f"  [green]✓[/green] Whisper model: {WHISPER_MODEL} (CPU mode)")
    console.print(f"  [green]✓[/green] Output file: {OUTPUT_FILE}")
    console.print()

    if errors:
        console.print("[bold red]✗ Configuration errors — please fix before running:[/bold red]")
        for err in errors:
            console.print(f"  [red]• {err}[/red]")
        console.print()
        sys.exit(1)

    console.print(Rule("[bold green]Configuration OK — Starting Pipeline[/bold green]", style="green"))
    console.print()


def print_video_summary(profile: dict, video_index: int) -> None:
    """
    Print a condensed, human-readable summary of a per-video profile.

    We print a summary at this stage (not the full JSON) to keep the
    terminal readable during processing. The full output comes at the end.

    Args:
        profile:     Per-video profile dict from extract_video_profile().
        video_index: 1-based index for table title labelling.
    """
    table = Table(
        title=f"📹 Video {video_index} — Profile Summary",
        show_header=False,
        border_style="blue",
        min_width=65,
        padding=(0, 1),
    )
    table.add_column("Field", style="cyan bold", width=18)
    table.add_column("Value", style="white")

    table.add_row("Topic", profile.get("topic", "N/A"))
    table.add_row("Hook Type", profile.get("hook_type", "N/A"))
    table.add_row("Structure", profile.get("structure", "N/A"))
    table.add_row("Tone", profile.get("tone", "N/A"))
    table.add_row("Pacing", profile.get("pacing", "N/A"))

    phrases = profile.get("key_phrases", [])
    if phrases:
        table.add_row("Key Phrase", f'"{phrases[0]}"')

    console.print(table)
    console.print()


def main() -> None:
    """
    Main orchestration function — runs the full pipeline end-to-end.

    This function acts as the "director": it calls specialised functions from
    each module in sequence. Keeping orchestration logic here (rather than
    inside module files) makes the pipeline easy to read, modify, and test.
    """

    # ─── STAGE 0: Initialisation ───────────────────────────────────────────────
    print_banner()
    validate_configuration()

    # Create the temp directory for audio files if it doesn't exist
    os.makedirs(TEMP_AUDIO_DIR, exist_ok=True)

    # ─── Initialise shared components ─────────────────────────────────────────
    # We initialise all long-lived objects BEFORE the video loop to avoid
    # repeated model loading. Key objects:
    #   - vector_store: ChromaDB + embedding model (loads ~90MB model once)
    #   - video_chain: stateless LCEL chain (prompt | llm | parser)
    #   - creator_chain: stateless LCEL chain for synthesis
    #   - retriever: wraps vector_store for similarity search
    console.print(Rule("[bold yellow]Initialising AI Components[/bold yellow]", style="yellow"))

    console.print()
    vector_store = initialize_vector_store(CHROMA_PERSIST_DIR, COLLECTION_NAME)

    console.print("\n[bold yellow]⚙ Creating LLM chains...[/bold yellow]")
    video_chain = create_video_profiler_chain()
    console.print("  [green]✓ Video profiler chain ready (LCEL: prompt | llm | JsonOutputParser)[/green]")

    creator_chain = create_creator_profile_chain()
    console.print("  [green]✓ Creator profile chain ready[/green]")

    retriever = get_retriever(vector_store, k=RAG_TOP_K)

    console.print()
    console.print(Rule("[bold green]Initialisation Complete[/bold green]", style="green"))
    console.print()

    # ─── STAGES 1 + 2 + 3: Per-Video Processing Loop ──────────────────────────
    # We process videos SEQUENTIALLY (not in parallel) for two reasons:
    #   1. Whisper is CPU-bound — parallel runs would thrash the processor.
    #   2. One LLM call at a time — a local model is CPU-bound, Groq is rate-limited.

    # ── Resolve video sources based on INPUT_MODE ─────────────────────────────
    if INPUT_MODE == "local":
        console.print(Rule("[bold cyan]Input Mode: Local Videos[/bold cyan]", style="cyan"))
        console.print(f"\n  [cyan]📂 Scanning:[/cyan] {LOCAL_VIDEO_DIR}")
        try:
            video_sources = get_local_videos(LOCAL_VIDEO_DIR)
        except ValueError as e:
            console.print(f"\n[bold red]✗ {e}[/bold red]")
            sys.exit(1)
    else:
        console.print(Rule("[bold cyan]Input Mode: YouTube URLs[/bold cyan]", style="cyan"))
        video_sources = SAMPLE_VIDEO_URLS

    console.print()
    console.print(Rule(
        f"[bold cyan]Processing {len(video_sources)} Videos[/bold cyan]",
        style="cyan"
    ))

    per_video_profiles = []

    for idx, source in enumerate(video_sources, start=1):

        # ── STAGE 1: Transcription ────────────────────────────────────────────
        console.print(
            f"\n[bold cyan]▶ STAGE 1 — Transcription[/bold cyan] "
            f"[dim](Video {idx}/{len(video_sources)})[/dim]"
        )

        try:
            if INPUT_MODE == "local":
                # Local file: pass directly to Whisper (no download needed)
                transcript = process_local_video(
                    video_path=source,
                    video_index=idx,
                    total=len(video_sources),
                    model_size=WHISPER_MODEL,
                    language=WHISPER_LANGUAGE,
                    task=WHISPER_TASK,
                )
            else:
                # YouTube URL: download audio first, then transcribe
                transcript = process_video(
                    url=source,
                    video_index=idx,
                    total=len(video_sources),
                    output_dir=TEMP_AUDIO_DIR,
                    model_size=WHISPER_MODEL,
                    language=WHISPER_LANGUAGE,
                    task=WHISPER_TASK,
                )
        except (ValueError, RuntimeError, FileNotFoundError) as e:
            console.print(f"  [red]✗ Transcription failed for video {idx}: {e}[/red]")
            console.print("  [yellow]  Skipping this video...[/yellow]")
            continue

        # Show a quick transcript preview for sanity-checking
        preview = transcript[:120].replace("\n", " ")
        if len(transcript) > 120:
            preview += "..."
        console.print(f"  [dim]Preview: \"{preview}\"[/dim]")

        # ── STAGE 2: Per-Video Profile Extraction ─────────────────────────────
        console.print(
            f"\n[bold cyan]▶ STAGE 2 — Profile Extraction[/bold cyan] "
            f"[dim](Video {idx}/{len(SAMPLE_VIDEO_URLS)})[/dim]"
        )

        try:
            profile = extract_video_profile(
                chain=video_chain,
                transcript=transcript,
                video_url=source,  # works for both file path and URL
                max_retries=MAX_JSON_RETRIES,
            )
            per_video_profiles.append(profile)
        except RuntimeError as e:
            console.print(f"  [red]✗ Profile extraction failed: {e}[/red]")
            console.print("  [yellow]  Skipping storage for this video...[/yellow]")
            continue

        print_video_summary(profile, idx)

        # ── STAGE 3: ChromaDB Storage ─────────────────────────────────────────
        console.print(
            f"[bold cyan]▶ STAGE 3 — Storing in ChromaDB[/bold cyan] "
            f"[dim](Video {idx}/{len(video_sources)})[/dim]"
        )

        try:
            store_video_profile(vector_store, profile, idx, transcript=transcript,
                                language=transcriber.last_language)
        except Exception as e:
            console.print(f"  [red]✗ ChromaDB storage failed: {e}[/red]")

        # ── Rate limit guard ──────────────────────────────────────────────────
        if idx < len(video_sources):
            console.print(
                f"\n  [dim]⏳ Waiting {API_CALL_DELAY}s "
                f"(LLM rate limit guard)...[/dim]"
            )
            time.sleep(API_CALL_DELAY)

    # Abort if no profiles were successfully extracted
    if not per_video_profiles:
        console.print(
            "\n[bold red]✗ No video profiles were extracted. "
            "Check your video files and LLM setup.[/bold red]"
        )
        sys.exit(1)

    console.print()
    console.print(Rule(
        f"[bold green]Per-Video Processing Complete "
        f"({len(per_video_profiles)}/{len(video_sources)} videos)[/bold green]",
        style="green"
    ))
    console.print()

    # ─── STAGE 4: RAG — Master Creator Profile Synthesis ─────────────────────
    console.print(Rule(
        "[bold magenta]STAGE 4 — RAG: Master Creator Profile Synthesis[/bold magenta]",
        style="magenta"
    ))
    console.print()

    # This query is deliberately broad — we want the retriever to surface
    # all video profiles, not just ones matching a narrow keyword.
    # With k=3 and 3 videos this retrieves everything, but a well-formed
    # query is important for when the collection scales to dozens of videos.
    rag_query = (
        "Analyze the content style, tone, pacing, hook strategies, and target audience "
        "of this creator based on all their videos. Include recurring topics, signature "
        "phrases, and overall content patterns."
    )

    try:
        creator_profile = build_creator_profile(
            retriever=retriever,
            chain=creator_chain,
            query=rag_query,
            max_retries=MAX_JSON_RETRIES,
        )
    except RuntimeError as e:
        console.print(f"\n[bold red]✗ Creator profile synthesis failed: {e}[/bold red]")
        sys.exit(1)

    # ─── STAGE 5: Output ───────────────────────────────────────────────────────
    console.print()
    console.print(Rule("[bold green]STAGE 5 — Final Output[/bold green]", style="green"))
    console.print()

    # Pretty-print the full JSON to terminal
    profile_json_str = json.dumps(creator_profile, indent=2, ensure_ascii=False)
    console.print(Panel(
        f"[green]{profile_json_str}[/green]",
        title="[bold white]🎯 Master Creator Profile[/bold white]",
        border_style="green",
        expand=False,
    ))

    # Save to file
    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(creator_profile, f, indent=2, ensure_ascii=False)
        abs_path = str(Path(OUTPUT_FILE).resolve())
        console.print(f"\n  [bold green]✓ Saved to:[/bold green] {abs_path}")
    except IOError as e:
        console.print(f"\n  [yellow]⚠ Could not save to file: {e}[/yellow]")

    # ─── Completion Summary ────────────────────────────────────────────────────
    console.print()
    console.print(Panel(
        f"  [bold white]Pipeline completed successfully![/bold white]\n\n"
        f"  Videos processed:    [cyan]{len(per_video_profiles)}/{len(SAMPLE_VIDEO_URLS)}[/cyan]\n"
        f"  Creator niche:       [cyan]{creator_profile.get('creator_niche', 'N/A')}[/cyan]\n"
        f"  Dominant tone:       [cyan]{creator_profile.get('dominant_tone', 'N/A')}[/cyan]\n"
        f"  Avg pacing:          [cyan]{creator_profile.get('avg_pacing', 'N/A')}[/cyan]\n"
        f"  ChromaDB:            [cyan]{CHROMA_PERSIST_DIR}/[/cyan]\n"
        f"  Output file:         [cyan]{OUTPUT_FILE}[/cyan]",
        title="[bold green]✅ Module 1 Complete[/bold green]",
        border_style="green",
    ))
    console.print()


# ─── Entry Point ──────────────────────────────────────────────────────────────
# `if __name__ == "__main__"` ensures main() only runs when this script is
# executed directly (`python main.py`), not when imported as a module.
if __name__ == "__main__":
    main()
