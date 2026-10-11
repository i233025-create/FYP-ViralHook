"""
main.py — Module 2: Multimodal RAG Pipeline
============================================
CLI entry point. Mirrors module1/main.py structure.

Usage:
  cd "fyp poc/module2_multimodal_rag"
  python main.py

Or from workspace root:
  module1_style_extraction\\venv\\Scripts\\python.exe module2_multimodal_rag/main.py

What it does:
  1. Scans input_videos/ folder (shared with module1)
  2. For each video runs the full multimodal pipeline:
       Whisper → text profile → text embedding
       FFmpeg frames → CLIP → visual embedding
       PySceneDetect → shot features
       librosa → audio features
  3. Stores all named vectors + payload in Qdrant (in-memory)
  4. Synthesises multimodal master creator profile
  5. Saves enhanced creator_profile_multimodal.json

Output:
  module2_multimodal_rag/creator_profile_multimodal.json
"""

import sys
import os
import json
from pathlib import Path

# ── Workspace root ─────────────────────────────────────────────────────────────
_MODULE2_DIR    = Path(__file__).parent.resolve()
_WORKSPACE_ROOT = _MODULE2_DIR.parent.resolve()
sys.path.insert(0, str(_WORKSPACE_ROOT))

from dotenv import load_dotenv
load_dotenv(_WORKSPACE_ROOT / "module1_style_extraction" / ".env")
load_dotenv(_WORKSPACE_ROOT / ".env")

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

# ── Config ─────────────────────────────────────────────────────────────────────
INPUT_VIDEOS_DIR     = _WORKSPACE_ROOT / "module1_style_extraction" / "input_videos"
OUTPUT_PROFILE_PATH  = _MODULE2_DIR / "creator_profile_multimodal.json"
ALLOWED_EXTENSIONS   = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
WHISPER_MODEL        = "base"


def main():
    console.print(Panel.fit(
        "[bold cyan]Module 2: Multimodal RAG Pipeline[/bold cyan]\n"
        "  → Transcription:   Whisper (reused from Module 1)\n"
        "  → Text Profile:    LLM via Groq\n"
        "  → Visual:          CLIP ViT-B/32 (open-clip-torch)\n"
        "  → Shot Detection:  PySceneDetect\n"
        "  → Audio:           librosa\n"
        "  → Vector Store:    Qdrant (in-memory, named vectors)",
        title="🎬 ViralHook — Multimodal Creator Analysis",
        border_style="cyan",
    ))

    # ── Pre-flight checks ──────────────────────────────────────────────────────
    groq_api_key = os.getenv("GROQ_API_KEY", "")
    if not groq_api_key:
        console.print("[red]✗ GROQ_API_KEY not found in .env[/red]")
        sys.exit(1)
    console.print(f"[green]✓ GROQ_API_KEY detected[/green]")

    if not INPUT_VIDEOS_DIR.exists():
        console.print(f"[red]✗ Input video directory not found: {INPUT_VIDEOS_DIR}[/red]")
        console.print("  Create it and add your videos there.")
        sys.exit(1)

    video_files = [
        f for f in sorted(INPUT_VIDEOS_DIR.iterdir())
        if f.suffix.lower() in ALLOWED_EXTENSIONS
    ]

    if not video_files:
        console.print(f"[red]✗ No videos found in {INPUT_VIDEOS_DIR}[/red]")
        sys.exit(1)

    console.print(f"[green]✓ Found {len(video_files)} video(s) to process[/green]")
    for vf in video_files:
        size_mb = vf.stat().st_size / (1024 * 1024)
        console.print(f"  · {vf.name} ({size_mb:.1f} MB)")

    # ── Initialise Qdrant ──────────────────────────────────────────────────────
    console.print("\n[cyan]Initialising Qdrant (in-memory)...[/cyan]")
    from module2_multimodal_rag.qdrant_store import create_client, init_collection
    qdrant_client = create_client()
    init_collection(qdrant_client)
    console.print("[green]✓ Qdrant ready[/green]")

    # ── Process each video ─────────────────────────────────────────────────────
    console.print(f"\n[cyan]Processing {len(video_files)} video(s)...[/cyan]")

    from module2_multimodal_rag.multimodal_profiler import (
        process_video,
        build_multimodal_creator_profile,
    )

    all_results = []
    for idx, video_path in enumerate(video_files, start=1):
        console.rule(f"[bold]Video {idx}/{len(video_files)}: {video_path.name}[/bold]")
        result = process_video(
            video_path=str(video_path),
            video_index=idx,
            total_videos=len(video_files),
            qdrant_client=qdrant_client,
            groq_api_key=groq_api_key,
            whisper_model_size=WHISPER_MODEL,
            verbose=True,
        )
        all_results.append(result)

        if result["errors"]:
            console.print(f"  [yellow]⚠ {len(result['errors'])} non-fatal error(s):[/yellow]")
            for err in result["errors"]:
                console.print(f"    · {err}")

    # ── Build master multimodal profile ───────────────────────────────────────
    console.rule("[bold cyan]Synthesising Multimodal Creator Profile[/bold cyan]")
    console.print("Running RAG over stored profiles + aggregating multimodal stats...")

    multimodal_profile = build_multimodal_creator_profile(
        all_video_results=all_results,
        qdrant_client=qdrant_client,
        groq_api_key=groq_api_key,
    )

    # ── Save to disk ───────────────────────────────────────────────────────────
    with open(OUTPUT_PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(multimodal_profile, f, indent=2, ensure_ascii=False)

    # ── Save Qdrant snapshot for scripting agent to reload ─────────────────────
    # Scripting agent reads this file to load multimodal retrieval context
    from module2_multimodal_rag.qdrant_store import get_all_profiles
    snapshot_path = _MODULE2_DIR / "qdrant_snapshot.json"
    snapshot_points = []
    for r in all_results:
        if r.get("text_vector") and r.get("visual_vector"):
            snapshot_points.append({
                "text_vector":   r["text_vector"],
                "visual_vector": r["visual_vector"],
                "payload":       r.get("payload", {}),
            })
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump({"points": snapshot_points}, f, ensure_ascii=False)
    console.print(f"[green]✓ Qdrant snapshot saved ({len(snapshot_points)} vectors) → qdrant_snapshot.json[/green]")

    console.print(f"\n[green]✓ Multimodal creator profile saved to:[/green]")
    console.print(f"  {OUTPUT_PROFILE_PATH}")

    # ── Summary ────────────────────────────────────────────────────────────────
    console.print(Panel.fit(
        f"[bold green]Pipeline Complete[/bold green]\n\n"
        f"  Videos processed:   {len(all_results)}\n"
        f"  Stored in Qdrant:   {sum(1 for r in all_results if 'point_id' in r)}\n"
        f"  Visual pacing:      {multimodal_profile.get('visual_analysis', {}).get('visual_pacing', 'N/A')}\n"
        f"  Speech rate:        {multimodal_profile.get('audio_analysis', {}).get('speech_rate_label', 'N/A')}\n"
        f"  Dominant hook:      {multimodal_profile.get('signature_hooks', ['N/A'])[0] if multimodal_profile.get('signature_hooks') else 'N/A'}\n"
        f"  Output:             creator_profile_multimodal.json",
        title="✅ Module 2 Done",
        border_style="green",
    ))

    # ── Print per-video breakdown ──────────────────────────────────────────────
    per_video = multimodal_profile.get("per_video_profiles", [])
    if per_video:
        console.print("\n[bold]Per-Video Analysis:[/bold]")
        for vp in per_video:
            console.print(
                f"  · {vp['video_id']:<22} "
                f"Hook: {str(vp.get('hook_type','?')):<20} "
                f"Pacing: {str(vp.get('visual_pacing','?')):<20} "
                f"Speech: {vp.get('speech_rate_wpm', 0):.0f}wpm | "
                f"TH: {vp.get('talking_head_pct', 0)*100:.0f}%"
            )


if __name__ == "__main__":
    main()
