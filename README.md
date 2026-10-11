# ViralHook — Automated Short-Form Content Creation Pipeline
### Final Year Project (FYP) — Proof of Concept

> An AI-powered pipeline that analyses a creator's content style, identifies trending topics, and generates personalised short-form video scripts — combining RAG, LangGraph, YouTube Data API, and LLM-based evaluation.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [System Architecture](#system-architecture)
3. [Tech Stack](#tech-stack)
4. [Project Structure](#project-structure)
5. [Module 1: RAG-Based Style & Niche Extraction](#module-1-rag-based-style--niche-extraction)
6. [Pipeline: Research Agent](#pipeline-research-agent)
7. [Pipeline: Scripting Agent](#pipeline-scripting-agent)
8. [Shared Pipeline State](#shared-pipeline-state)
9. [Setup & Installation](#setup--installation)
10. [Running the Full Pipeline](#running-the-full-pipeline)
11. [Environment Variables](#environment-variables)
12. [Key Design Decisions](#key-design-decisions)
13. [FYP Research Contribution](#fyp-research-contribution)
14. [Known Limitations](#known-limitations)
15. [Future Work](#future-work)

---

## Project Overview

ViralHook is a proof-of-concept automated content creation pipeline for **faceless short-form video creators** (Instagram Reels, YouTube Shorts, TikTok). 

The system:
1. **Analyses** a creator's existing videos to extract their unique style fingerprint
2. **Discovers** trending topics in their niche using the YouTube Data API
3. **Generates** personalised video scripts in the creator's voice — and demonstrates that RAG + evaluator feedback measurably improves script quality over a baseline

The POC targets a single creator, processes 3–5 of their videos, and produces a complete content brief: trending topic + scene-by-scene script with timecodes, visuals, captions, and voiceover.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ViralHook Pipeline                                  │
│                                                                             │
│  ┌──────────────────────┐                                                   │
│  │   MODULE 1           │                                                   │
│  │   Style Extraction   │──► creator_profile.json ──► ChromaDB             │
│  │                      │    (tone, pacing, hooks,     (per-video profiles) │
│  │  Local Videos / URLs │     niche, audience)                              │
│  └──────────────────────┘                                                   │
│            │                                                                │
│            ▼                                                                │
│  ┌──────────────────────┐                                                   │
│  │   RESEARCH AGENT     │                                                   │
│  │   (LangGraph Node)   │──► research_output                               │
│  │                      │    (topic, trend_score,                           │
│  │  YouTube Data API    │     velocity, evidence)                           │
│  │  + Topic Clustering  │                                                   │
│  └──────────────────────┘                                                   │
│            │                                                                │
│            ▼                                                                │
│  ┌──────────────────────┐                                                   │
│  │   SCRIPTING AGENT    │                                                   │
│  │   (LangGraph Node)   │──► ScriptOutput                                  │
│  │                      │    (5 scenes × timecode,                          │
│  │  3 Modes:            │     clip_idea, caption,                           │
│  │  - no_history        │     voiceover)                                    │
│  │  - retrieval_only    │                                                   │
│  │  - full_pipeline     │                                                   │
│  └──────────────────────┘                                                   │
│                                                                             │
│  [Module 3: Visuals Agent — planned]                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Creator Videos (mp4/mov)
    │
    ▼
Whisper (tiny, CPU) ──► Transcript (English)
    │
    ▼
Groq LLM ──► Per-Video Profile JSON
    │            (topic, hook, tone, pacing, structure)
    ▼
ChromaDB ──► Embedded Vector Store
    │
    ▼
RAG Query ──► Master Creator Profile JSON
    │           (niche, signature_hooks, dominant_tone,
    │            avg_pacing, typical_structure, target_audience)
    ▼
YouTube Data API ──► Trend Scoring ──► Topic Clustering
    │                                      │
    │                                      ▼
    │                               Trending Topic
    │                                      │
    └──────────────────────────────────────┘
                                           │
                                           ▼
                                  Scripting Agent
                            (topic + creator profile + RAG)
                                           │
                                           ▼
                                  Final Script JSON
                            (5 scenes with full production brief)
```

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Language | Python 3.11 | Core runtime |
| Transcription | OpenAI Whisper (tiny, local) | Audio-to-text, CPU-only |
| LLM | Groq API (`openai/gpt-oss-20b`) | Profile extraction, script generation, evaluation |
| Embeddings | HuggingFace `all-MiniLM-L6-v2` | Local, CPU, 384-dim vectors |
| Vector Store | ChromaDB (local) | Persistent per-video profile storage |
| LLM Framework | LangChain (LCEL) + LangGraph | Chain composition + agent graph |
| Trend Research | YouTube Data API v3 | Real-time video trend data |
| Audio Download | yt-dlp + ffmpeg | YouTube audio extraction |
| Terminal UI | Rich | Formatted output, panels, progress |
| Config | python-dotenv | API key management |

---

## Project Structure

```
fyp poc/
│
├── README.md                          ← This file
│
├── module1_style_extraction/          ← Module 1: Creator Style Analysis
│   ├── main.py                        ← Pipeline entry point
│   ├── config.py                      ← All constants and settings
│   ├── transcriber.py                 ← Whisper transcription + yt-dlp download
│   ├── video_profiler.py              ← Per-video profile extraction (LCEL chain)
│   ├── vector_store.py                ← ChromaDB management
│   ├── creator_profiler.py            ← Master creator profile synthesis (RAG)
│   ├── requirements.txt               ← Python dependencies
│   ├── .env.example                   ← Environment variable template
│   ├── .env                           ← Your API keys (not committed)
│   ├── input_videos/                  ← Drop creator videos here (mp4/mov)
│   ├── chroma_db/                     ← ChromaDB vector store (auto-created)
│   ├── temp_audio/                    ← Temporary audio files (auto-deleted)
│   └── creator_profile.json          ← OUTPUT: Master creator profile
│
└── pipeline/                          ← LangGraph Pipeline (Research + Scripting)
    ├── state.py                       ← Shared PipelineState TypedDict + Pydantic models
    ├── requirements.txt               ← Additional pipeline dependencies
    ├── .env.example                   ← YouTube API key template
    ├── cache/                         ← YouTube API response cache (auto-created)
    │
    ├── agents/
    │   ├── __init__.py
    │   ├── research_agent.py          ← LangGraph node: YouTube trend research
    │   └── scripting_agent.py         ← LangGraph node: 3-mode script generation
    │
    ├── test_research_agent.py         ← Standalone research agent test
    └── test_scripting_comparison.py   ← Ablation comparison (all 3 scripting modes)
```

---

## Module 1: RAG-Based Style & Niche Extraction

### Purpose
Analyse a creator's existing videos to build a structured **creator profile** — their unique style fingerprint that the Scripting Agent uses to generate on-brand content.

### Pipeline Stages

**Stage 1 — Transcription**
- Input: Local video files (mp4/mov) from `input_videos/` or YouTube URLs
- Whisper `tiny` model transcribes each video on CPU (~6–30s per short video)
- `task="translate"` converts non-English audio to English automatically
- Character cleaning strips emoji/CJK/Cyrillic hallucinations from noisy audio

**Stage 2 — Per-Video Profile Extraction**
- Each transcript is sent to Groq LLM via an LCEL chain
- LLM extracts a structured JSON profile per video:
  ```json
  {
    "topic": "string",
    "hook_text": "string",
    "hook_type": "Contrarian | Curiosity Gap | Bold Claim | Question | Statistic | Story",
    "structure": "Hook → Problem → Solution",
    "tone": "Conversational | Technical | Humorous | Inspirational | Educational",
    "pacing": "Slow | Moderate | Fast-paced",
    "key_phrases": ["list of 3-5 phrases"],
    "transcript_summary": "2-3 sentence summary"
  }
  ```
- Retry logic (max 2 attempts) handles JSON parse failures

**Stage 3 — Vector Storage**
- Each per-video profile is converted to prose-style text and embedded using `all-MiniLM-L6-v2`
- Stored in ChromaDB with deterministic document IDs (`video_1`, `video_2`, ...) — prevents duplicates on re-runs

**Stage 4 — RAG Synthesis**
- ChromaDB is queried to retrieve all video profiles as context
- Groq LLM synthesises a **master creator profile**:
  ```json
  {
    "creator_niche": "string",
    "signature_hooks": ["list"],
    "dominant_tone": "string",
    "avg_pacing": "string",
    "typical_structure": "string",
    "target_audience": "string",
    "recurring_topics": ["list"],
    "content_style_summary": "string",
    "visual_style_suggestions": ["list"]
  }
  ```
- Saved to `creator_profile.json` and printed to terminal

### Configuration (`config.py`)

| Setting | Default | Description |
|---------|---------|-------------|
| `INPUT_MODE` | `"local"` | `"local"` for video files, `"youtube"` for URLs |
| `WHISPER_MODEL` | `"tiny"` | Whisper model size (tiny/base/small) |
| `WHISPER_TASK` | `"translate"` | Translate to English or transcribe original |
| `WHISPER_LANGUAGE` | `None` | Auto-detect language |
| `GROQ_MODEL` | `openai/gpt-oss-20b` | Groq model ID |
| `RAG_TOP_K` | `3` | Documents retrieved per RAG query |
| `API_CALL_DELAY` | `2.0s` | Groq rate limit guard |

### Running Module 1

```powershell
cd "module1_style_extraction"
# Activate venv
.\venv\Scripts\Activate.ps1
# Add ffmpeg to PATH (Windows)
$env:PATH = $env:PATH + ";C:\ffmpeg-9.0.1-essentials_build\bin"
# Clear previous run data
Remove-Item -Recurse -Force "chroma_db" -ErrorAction SilentlyContinue
Remove-Item -Force "creator_profile.json" -ErrorAction SilentlyContinue
# Run
python main.py
```

---

## Pipeline: Research Agent

### Purpose
Find the **single most trending topic** in the creator's niche using real YouTube data, scored by velocity and engagement, clustered by topical coherence.

### How It Works

**Step 1 — Keyword Expansion (static)**
- Maps creator niche to 5–8 related YouTube search keywords using a hand-crafted dictionary
- No LLM call — fast and deterministic
- Example: `"Personal Growth"` → `["self improvement tips", "morning routine productivity", "growth mindset", "discipline habits", ...]`

**Step 2 — YouTube Data API Search**
- `search.list` per keyword: videos published in last 5 days, ordered by viewCount
- `videos.list` (batched): fetches viewCount, likeCount, commentCount, publishedAt, description
- Results cached locally in `pipeline/cache/` (TTL = 6 hours) to preserve API quota

**Step 3 — Trend Scoring**
```
velocity         = viewCount / hours_since_published
engagement_rate  = (likeCount + commentCount) / viewCount
trend_score      = 0.6 × norm_velocity + 0.4 × norm_engagement
```
Both metrics are min-max normalised across all candidate videos.

**Step 4 — Topic Clustering**
- Extracts content keywords from title + description (strips stopwords, hashtags, emoji)
- Builds a Jaccard similarity matrix across top 30 scored videos
- Greedy clustering with overlap threshold 0.10
- Scores each cluster: `sum(trend_scores) × √(cluster_size)` — rewards coherent multi-video topics over single viral outliers
- Minimum cluster size = 2 (single-video topics flagged as `low_confidence: true`)
- Synthesises a clean topic name from shared keywords across the winning cluster

**Output (`research_output`):**
```json
{
  "topic": "Morning Routine",
  "trend_score": 0.3108,
  "trend_signals": {
    "velocity": 117.96,
    "engagement_rate": 0.0928
  },
  "niche": "Personal Growth",
  "supporting_evidence": [
    {"video_title": "...", "channel": "...", "views": 81471, "published_hours_ago": 43.9},
    {"video_title": "...", "channel": "...", "views": 41756, "published_hours_ago": 93.8}
  ],
  "related_keywords": ["self improvement tips", "morning routine productivity", ...],
  "cluster_size": 3,
  "low_confidence": false,
  "source": "youtube_data_api"
}
```

**Fallback Chain:**
1. YouTube Data API (primary)
2. LLM-generated topic via Groq (if API fails/quota exceeded)
3. Static hardcoded topic by niche (if Groq also unavailable)

### Running the Research Agent

```powershell
cd "C:\Users\lenovo\Desktop\fyp poc"
python pipeline\test_research_agent.py "Personal Growth"
# Pass any niche as argument — defaults to last research output if omitted
```

### API Quota
- `search.list`: 100 units × ~7 keywords = ~700 units per run
- `videos.list`: ~5 units per run
- Free quota: 10,000 units/day → ~13 full runs/day
- Caching means repeated runs in the same day use 0 quota

---

## Pipeline: Scripting Agent

### Purpose
Generate a **30-second short-form video script** (5 scenes) about the trending topic, styled to match the creator's profile. Implements three modes for ablation comparison.

### The Trend → Script Connection
The `research_output.topic` (e.g., `"Morning Routine"`) is passed directly as the script topic. All three modes write a script *about* this trending topic. The modes differ only in how much creator context they receive.

### Three Modes (Ablation Study)

#### Mode 1 — `no_history` (Baseline)
**What the LLM receives:** Topic + creator's dominant hook type and structure (extracted from profile for fair comparison)

**What it does NOT receive:** Creator examples, tone, pacing, target audience, style summary

**Purpose:** Baseline — what does AI produce without personalisation?

**LLM calls:** 1

#### Mode 2 — `retrieval_only` (RAG)
**What the LLM receives:**
- Topic
- Per-video profile examples retrieved from ChromaDB (few-shot demonstrations of creator's real content)
- Full `creator_profile.json` as style guide (tone, pacing, hooks, audience, structure, style summary)

**Purpose:** Does RAG context alone improve style alignment?

**LLM calls:** 1

#### Mode 3 — `full_pipeline` (RAG + Evaluation + Feedback)
**What the LLM receives:** Everything from Mode 2 + evaluator feedback

**Process:**
1. Generate initial script (same as Mode 2)
2. Evaluator LLM scores the script on three criteria (0–10 each):
   - `style_match`: Does it sound like this creator?
   - `hook_strength`: How scroll-stopping is the opening?
   - `structure_adherence`: Does it follow their typical structure?
3. If `overall < 7.0`: regenerate with feedback injected into prompt
4. Max 2 regeneration attempts — keeps best-scoring version

**Purpose:** Does evaluation + feedback further improve output beyond retrieval alone?

**LLM calls:** 2–4 (generation + evaluation + optional regeneration × 2)

### Script Output Schema

```json
{
  "script_id": 1,
  "concept_name": "Morning Power Routine",
  "hook_type": "Bold Claim",
  "scenes": [
    {
      "timecode": "0:00-0:06",
      "clip_idea": "Creator stands in bright bathroom, flips timer to 30 minutes",
      "caption": "30 Minutes, Flawless Skin",
      "voiceover": "30 minutes saved, flawless skin — my morning hack!"
    },
    ...4 more scenes
  ]
}
```

### Running the Scripting Comparison

```powershell
cd "C:\Users\lenovo\Desktop\fyp poc"
python pipeline\test_scripting_comparison.py
# Automatically uses topic from last research agent run
# Or pass a topic directly:
python pipeline\test_scripting_comparison.py "Morning Routine"
```

Output includes:
- Full script for each mode (5 scenes with all fields)
- Evaluator scores for Mode 3 (style, hook, structure, overall, feedback)
- Side-by-side summary table
- Saved to `pipeline/test_scripting_comparison_output.json`

---

## Shared Pipeline State

All agents read from and write to a shared `PipelineState` TypedDict (`pipeline/state.py`). This is the LangGraph convention — nodes return partial state updates that are automatically merged.

```python
class PipelineState(TypedDict):
    # Entry point
    creator_id: str
    creator_niche: str
    creator_profile: dict           # from creator_profile.json

    # Research Agent outputs
    research_output: Optional[dict]
    research_error: Optional[str]

    # Scripting Agent outputs
    scripting_output: Optional[ScriptingOutput]
    scripting_error: Optional[str]

    # Visuals Agent outputs (Module 3 — planned)
    visual_prompts: Optional[list]
    visual_error: Optional[str]
```

Pydantic models for typed scripting output:
- `SceneOutput` — one scene (timecode, clip_idea, caption, voiceover)
- `ScriptOutput` — one script (script_id, concept_name, hook_type, scenes)
- `ScriptingOutput` — container (scripts list + optional final_script)

---

## Setup & Installation

### Prerequisites
- Python 3.11
- ffmpeg installed and on PATH ([Windows download](https://ffmpeg.org/download.html))
- Groq API key (free at [console.groq.com](https://console.groq.com))
- YouTube Data API v3 key (free at [console.cloud.google.com](https://console.cloud.google.com))

### Install Dependencies

```powershell
cd "module1_style_extraction"
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
# Install git-based whisper (fixes pkg_resources issue on Python 3.11)
pip install "openai-whisper @ git+https://github.com/openai/whisper.git"
# Install pipeline dependencies
pip install pytrends==4.9.2 langgraph==0.2.28 pydantic==2.7.1
pip install "langchain-groq==0.2.3"
pip install requests
```

### Configure API Keys

```powershell
copy .env.example .env
# Edit .env and add:
# GROQ_API_KEY=your_key_here
# YOUTUBE_API_KEY=your_key_here
```

---

## Running the Full Pipeline

### Step 1 — Prepare Videos
Drop 3–5 creator videos (mp4/mov/mkv) into:
```
module1_style_extraction/input_videos/
```

### Step 2 — Run Module 1 (Style Extraction)
```powershell
cd "module1_style_extraction"
.\venv\Scripts\Activate.ps1
$env:PATH = $env:PATH + ";C:\ffmpeg-9.0.1-essentials_build\bin"
Remove-Item -Recurse -Force "chroma_db" -ErrorAction SilentlyContinue
Remove-Item -Force "creator_profile.json" -ErrorAction SilentlyContinue
python main.py
```
**Output:** `creator_profile.json` + populated ChromaDB

### Step 3 — Run Research Agent (Trend Discovery)
```powershell
cd "C:\Users\lenovo\Desktop\fyp poc"
python pipeline\test_research_agent.py "Your Creator Niche"
```
**Output:** `pipeline/test_research_output.json` with trending topic

### Step 4 — Run Scripting Comparison (Script Generation)
```powershell
python pipeline\test_scripting_comparison.py
```
**Output:** `pipeline/test_scripting_comparison_output.json` with all 3 scripts + scores

---

## Environment Variables

```env
# Required for Module 1 and Scripting Agent
GROQ_API_KEY=gsk_...

# Required for Research Agent
YOUTUBE_API_KEY=AIza...
```

Place in: `module1_style_extraction/.env`

---

## Key Design Decisions

**Why Whisper `tiny` instead of `base`?**
CPU-only constraint on the dev machine. `tiny` handles 60-second reels in ~6–30 seconds. Upgrade to `base` for better accuracy at ~2× the processing time.

**Why `task="translate"` instead of `task="transcribe"`?**
Target creators may post in Urdu, Hindi, or mixed-language audio. Translation to English ensures the LLM receives clean text regardless of input language.

**Why ChromaDB locally instead of a cloud vector DB?**
Zero infrastructure cost, no API keys, persists between runs, sufficient for a 3–10 video POC.

**Why `langchain-community` embeddings instead of `langchain-huggingface`?**
`langchain-huggingface==0.0.3` is incompatible with Pydantic v2.7+. The community package provides the same `HuggingFaceEmbeddings` class without the Pydantic v1 dependency.

**Why static keyword expansion instead of LLM for niche → keywords?**
Avoids an extra API call, deterministic output, and the static map covers all common niches well enough for a POC. The LLM is reserved for higher-value tasks (profiling, scripting, evaluation).

**Why YouTube Data API instead of Google Trends/pytrends?**
pytrends returns 400/404 errors when accessed from Pakistan due to regional IP blocking. YouTube Data API provides richer data (actual viewCount, likeCount, publish time) and works reliably.

**Why cluster scoring uses `sum(trend_scores) × √(cluster_size)`?**
Rewards topics with multiple supporting videos over single viral outliers. A clickbait video with 1M views in 1 hour should not outrank a coherent cluster of 3 videos each with 100K views — the cluster represents a genuine trend.

**Why cap `full_pipeline` regeneration at 2 attempts?**
Each attempt costs ~2 Groq API calls (generation + evaluation). The free tier allows 14,400 requests/day but we want the demo to run quickly. 2 attempts gives the model a real second chance without making the user wait 30+ seconds.

---

## FYP Research Contribution

The ablation study built into the Scripting Agent is the core research contribution:

| Mode | Context | Expected Quality |
|------|---------|-----------------|
| `no_history` | Topic only | Generic — no creator identity |
| `retrieval_only` | Topic + RAG + profile | On-brand — matches creator style |
| `full_pipeline` | Topic + RAG + profile + evaluator feedback | On-brand + refined — measurably higher scores |

This demonstrates that:
1. RAG-based creator context significantly improves style alignment (Mode 1 → Mode 2)
2. LLM-based evaluation + feedback further improves quality (Mode 2 → Mode 3)
3. The improvement is **quantifiable** via evaluator scores (not just subjective)

This is a standard ablation study design — removing one component at a time to isolate its contribution — which is well-accepted in NLP/AI research papers.

---

## Known Limitations

- **Whisper `tiny` accuracy:** Noisy or music-heavy videos may produce garbled transcripts. Upgrade to `base` for better accuracy. Music-only reels (no voice) will produce empty transcripts.
- **YouTube API quota:** 10,000 units/day free. Each research run costs ~700 units (~13 runs/day). Cached results reduce consumption significantly.
- **Cluster quality:** YouTube titles are often clickbait and share few keywords. The 0.10 Jaccard threshold is intentionally low; some clusters may still be weakly related. Future work: use embedding-based clustering.
- **LLM evaluation subjectivity:** The evaluator LLM's scores are not ground truth. They are consistent within a session but may vary across runs.
- **No Instagram integration:** Instagram's API does not support public content scraping. This is a planned future enhancement.
- **ChromaDB with 2–5 videos:** Very small corpus limits RAG diversity. The pipeline is designed to scale to 50–100 videos without code changes.

---

## Future Work

- **Module 3: Visuals Agent** — Generate AI image prompts per scene using the `clip_idea` field; integrate with Stable Diffusion or DALL-E
- **Streamlit UI** — Interactive web interface for the full pipeline (select videos, view scripts, edit and export)
- **Instagram Reels integration** — Via Meta Business API (requires approved business account)
- **Multi-creator support** — Separate ChromaDB collections per creator ID
- **Embedding-based clustering** — Replace Jaccard keyword overlap with sentence-transformer embeddings for better topic grouping
- **LangGraph full graph** — Wire Research → Scripting → Visuals as a complete compiled LangGraph with conditional edges
- **Script export** — Export final script as PDF storyboard or JSON for downstream tools
