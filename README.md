# ViralHook — AI-Driven Content Production System

> Final Year Project — School of Computing  
> Team: Rabeeha Kamran (i233025) · Zainab Tahir (i230042) · Hashaam Waheed Bhatti (i230002)  
> Supervisor: Dr. Muhammad Bilal

---

## What is ViralHook?

ViralHook is an AI-driven multi-agent content production system for social media creators. It automates the end-to-end workflow from creator onboarding → style extraction → trend research → script generation → production planning → XML/video export → publishing.

**Core technical contribution:** Creator-specific multimodal RAG that learns from a creator's existing videos (text + visual + audio) to generate personalised scripts — compared against a generic LLM baseline to demonstrate measurable improvement.

---

## Project Structure

```
fyp poc/
├── server.py                          # FastAPI backend (4 endpoints)
├── module1_style_extraction/          # Text-based RAG pipeline (baseline)
│   ├── main.py                        # CLI entry point
│   ├── transcriber.py                 # Whisper transcription
│   ├── video_profiler.py              # LLM per-video profile extraction
│   ├── vector_store.py                # ChromaDB storage
│   ├── creator_profiler.py            # RAG master profile synthesis
│   └── requirements.txt
├── module2_multimodal_rag/            # Multimodal RAG pipeline (contribution)
│   ├── main.py                        # CLI entry point
│   ├── frame_extractor.py             # FFmpeg frame sampling
│   ├── visual_embedder.py             # CLIP ViT-B/32 embeddings
│   ├── scene_detector.py              # PySceneDetect shot stats
│   ├── audio_analyzer.py              # librosa audio features
│   ├── qdrant_store.py                # Qdrant named vector storage
│   └── multimodal_profiler.py         # Pipeline orchestrator
├── pipeline/
│   ├── agents/
│   │   ├── research_agent.py          # LLM trend research
│   │   ├── scripting_agent.py         # 3-mode scripting + evaluator
│   │   └── video_agent.py             # Module 4: script → MP4 + measured evaluation
│   ├── video/                         # Module 4 building blocks (TTS, shots, assets,
│   │                                  #   SDXL, FFmpeg renderer, evaluator)
│   ├── state.py                       # LangGraph pipeline state
│   └── json_to_premiere_xml.py        # XMEML v4 export
├── frontend_extracted/frontend/       # React 18 + Vite + Tailwind
├── tests/backend/                     # pytest test suite (76 tests)
├── .github/workflows/
│   ├── ci.yml                         # CI: lint + test + frontend build
│   └── cd.yml                         # CD: Docker build + push to GHCR
├── Dockerfile.backend
├── Dockerfile.frontend
└── docker-compose.yml
```

---

## Branch Strategy

| Branch | Purpose | Rules |
|---|---|---|
| `main` | Stable, production-ready | Protected — PR required, CI must pass |
| `dev` | Integration branch | All features merge here first |
| `poc` | Mid-eval snapshot (frozen) | Do not push to this after mid eval |
| `feature/*` | Individual features | Branch from `dev`, PR back to `dev` |

### Workflow

```
feature/your-feature  →  PR to dev  →  PR to main
                          (review)      (CI must pass)
```

**Always branch from `dev`, never from `main` directly.**

```bash
git checkout dev
git pull origin dev
git checkout -b feature/your-feature-name
# ... do your work ...
git push -u origin feature/your-feature-name
# then open a PR to dev on GitHub
```

---

## Setup — Local Development

### Prerequisites

- Python 3.11
- Node.js 20+
- FFmpeg installed and on PATH
- Git

### Backend Setup

```bash
cd "fyp poc/module1_style_extraction"
python -m venv venv

# Windows
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install open-clip-torch scenedetect[opencv] librosa soundfile qdrant-client
pip install fastapi uvicorn python-multipart
```

Create your `.env` file:
```bash
# module1_style_extraction/.env
GROQ_API_KEY=your_groq_api_key_here
YOUTUBE_API_KEY=your_youtube_api_key_here   # optional
```

### Frontend Setup

```bash
cd "fyp poc/frontend_extracted/frontend"
npm install
```

---

## Running Locally

### Terminal 1 — Backend

```bash
cd "fyp poc"
module1_style_extraction\venv\Scripts\python.exe -m uvicorn server:app --reload --port 8000
```

### Terminal 2 — Frontend

```bash
cd "fyp poc/frontend_extracted/frontend"
npm run dev
```

Open `http://localhost:5173`

Set `USE_REAL_BACKEND = true` in `src/services/api.js` to connect to real backend.

---

## Full Local Stack (GPU machine)

Everything runs locally; only research needs a YouTube key.

```bash
# 1. Python env (Python 3.10+, CUDA GPU)
python -m venv .venv && source .venv/bin/activate
pip install torch==2.8.0 torchvision==0.23.0 --index-url https://download.pytorch.org/whl/cu128
pip install -r pipeline/requirements.txt -r pipeline/video/requirements.txt fastapi uvicorn python-dotenv

# 2. Local LLM
ollama serve &            # or ~/.local/ollama/bin/ollama serve
ollama pull qwen2.5:7b

# 3. Config: copy pipeline/.env.example → .env (repo root), fill YOUTUBE_API_KEY
#    (and PEXELS_API_KEY for stock footage)

# 4. Backend + frontend
uvicorn server:app --port 8000
cd frontend_extracted/frontend && npm run dev     # real backend is the default
```

Set `VITE_USE_REAL_BACKEND=false` in `frontend_extracted/frontend/.env.local` for an offline mock demo.

### Module 4 — Video Generation (CLI)

```bash
python -m pipeline.agents.video_agent                # personalised video
python -m pipeline.agents.video_agent --compare      # personalised vs generic + score deltas
# output: pipeline/output/video/<job>/final.mp4, timeline.json, evaluation.json
```

Personalised mode cuts at the creator's measured shot length, calibrates the
voiceover to their words-per-minute, uses karaoke captions when they use text
overlays, and ranks shots toward their visual look (Module 2 CLIP vectors).
The evaluator re-measures the rendered MP4 with Module 2's own extractors.

---

## Running the Pipeline (CLI)

### Module 1 — Text-based RAG (baseline)

```bash
# Place videos in module1_style_extraction/input_videos/
cd "fyp poc/module1_style_extraction"
venv\Scripts\python.exe main.py
# Output: creator_profile.json + ChromaDB populated
```

### Module 2 — Multimodal RAG

```bash
cd "fyp poc"
module1_style_extraction\venv\Scripts\python.exe module2_multimodal_rag/main.py
# Output: creator_profile_multimodal.json + qdrant_snapshot.json
```

---

## Running Tests

```bash
cd "fyp poc"
module1_style_extraction\venv\Scripts\python.exe -m pytest tests/backend/ -v
```

**76 tests, all must pass before pushing to main.**

Tests are designed to run without API keys or model downloads — safe for CI.

---

## Docker

### Run with docker-compose

```bash
# Copy your API key to root .env first
cp module1_style_extraction/.env .env

docker-compose up --build
```

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

### Pull pre-built images (after CD runs)

```bash
docker-compose pull
docker-compose up
```

---

## CI/CD Pipeline

### CI (runs on every push)

| Check | What it does |
|---|---|
| `backend-quality` | flake8 lint + pytest 76 tests |
| `frontend-quality` | npm ci + vite build |
| `CI Gate` | Both must pass — required for PRs to main |

### CD (runs on push to main only)

Builds and pushes Docker images to GitHub Container Registry:
- `ghcr.io/i233025-create/fyp-viralhook/backend:latest`
- `ghcr.io/i233025-create/fyp-viralhook/frontend:latest`

---

## Commit Message Format

Use clear, prefixed commit messages:

```
feat: add talking_head_pct via CLIP zero-shot classification
fix: downgrade numpy to <2 for ChromaDB compatibility
test: add qdrant store retrieval tests
docs: update README with Docker instructions
refactor: extract _parse_timecode to server utils
chore: update requirements.txt
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Server status |
| `GET` | `/onboarding/profile` | Load real creator profile |
| `POST` | `/research/trends` | LLM trend research |
| `POST` | `/script/generate` | 3-mode RAG scripting |
| `POST` | `/export/xml` | Premiere Pro XML export |
| `POST` | `/video/generate` | Start a video render job → `jobId` |
| `GET` | `/video/status/{jobId}` | Progress; timeline + evaluation when done |
| `GET` | `/video/file/{jobId}` | Rendered MP4 |

API docs available at `http://localhost:8000/docs` when server is running.

---

## Environment Variables

| Variable | Where | Required | Description |
|---|---|---|---|
| `GROQ_API_KEY` | `module1_style_extraction/.env` | ✅ Yes | LLM + Whisper API |
| `YOUTUBE_API_KEY` | `module1_style_extraction/.env` | ❌ Optional | Research agent (LLM fallback if not set) |

**Never commit `.env` files. They are in `.gitignore`.**  
For CI/CD, add `GROQ_API_KEY` as a GitHub Secret at:  
`Settings → Secrets and variables → Actions`

---

## Important Rules

1. **Never push directly to `main`** — always use a PR
2. **Never commit `.env` files or API keys**
3. **Never commit large files** — videos, model weights (`.pt`, `.bin`), `node_modules/`, `venv/`
4. **All tests must pass locally** before opening a PR
5. **`poc` branch is frozen** after mid eval — do not push to it
6. **One feature per branch** — keep PRs focused and reviewable
