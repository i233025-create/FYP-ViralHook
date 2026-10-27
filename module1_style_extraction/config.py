"""
config.py — Central Configuration for Module 1: RAG-based Style & Niche Extraction
====================================================================================
All constants, paths, model names, and runtime settings live here.
Keeping config in one place makes it easy to swap models or paths without
hunting through multiple files — a standard practice in production ML systems.
"""

import os
from dotenv import load_dotenv

# ─── Load Environment Variables ───────────────────────────────────────────────
# python-dotenv reads the .env file and injects its key=value pairs into
# os.environ, so the rest of the code can use os.getenv() safely.
load_dotenv()

# ─── API Keys ─────────────────────────────────────────────────────────────────
# We read the Groq API key from the environment (never hard-code secrets).
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

# ─── Model Configuration ──────────────────────────────────────────────────────

# Whisper model size. "tiny" is the smallest (~75 MB) and runs on CPU in
# reasonable time (~30 seconds per short video). For better accuracy,
# swap to "base" or "small", but expect longer processing times.
# NOTE: The model will be auto-downloaded from HuggingFace on first run.
WHISPER_MODEL: str = "tiny"

# Language for Whisper transcription.
# None = auto-detect
# "ur" = Urdu, "en" = English, "hi" = Hindi
# Experiment E1 (experiments/rag_e1/REPORT.md): auto-detect labels Pakistani
# Urdu–English speech as Hindi and writes Devanagari; forcing "en" gives clean
# English text, is 3–8× faster, and retrieval on it is far better (R@3 ~94% vs
# ~60% on Urdu script). The spoken language is still detected and stored.
WHISPER_LANGUAGE: str = "en"

# Whisper task mode.
# "transcribe" = output in the given language (English, with WHISPER_LANGUAGE="en")
# "translate"  = output in English regardless of input language
# E1 used "transcribe" with language="en"; keep the two together.
WHISPER_TASK: str = "transcribe"

# Sentence-Transformers model for generating text embeddings.
# "all-MiniLM-L6-v2" is a compact (~90 MB) but high-quality model that
# produces 384-dimensional embeddings. Runs on CPU without GPU.
# NOTE: Downloaded automatically on first use via sentence-transformers library.
EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

# Groq LLM model ID. "llama3-8b-8192" is Meta's LLaMA 3 8B parameter model
# hosted on Groq's ultra-fast inference API (free tier available).
# 8192 is the context window size (tokens) — plenty for our transcript + prompt.
GROQ_MODEL: str = "openai/gpt-oss-20b"

# ─── Storage Paths ────────────────────────────────────────────────────────────

# Directory where ChromaDB persists its vector index between runs.
# ChromaDB uses SQLite + its own file format under this folder.
# If the folder doesn't exist, ChromaDB creates it automatically.
CHROMA_PERSIST_DIR: str = "./chroma_db"

# ChromaDB collection name — think of it as a "table" in a SQL database.
# All per-video profile documents are stored in this collection.
COLLECTION_NAME: str = "video_profiles"

# Temporary folder for downloaded audio files.
# Files here are deleted after transcription to save disk space.
TEMP_AUDIO_DIR: str = "./temp_audio"

# Path where the final master creator profile JSON will be saved.
OUTPUT_FILE: str = "creator_profile.json"

# ─── Input Mode ───────────────────────────────────────────────────────────────
# Controls where the pipeline reads video input from.
# "youtube" — downloads from YouTube URLs defined in SAMPLE_VIDEO_URLS below.
# "local"   — reads video files (mp4, mov, mkv, avi, webm) from LOCAL_VIDEO_DIR.
#             Just drop your video files into the input_videos/ folder and run.
INPUT_MODE: str = "local"  # Switch to "youtube" to use URLs instead

# Directory to scan for local video files when INPUT_MODE = "local"
LOCAL_VIDEO_DIR: str = "./input_videos"

# ─── Sample YouTube Shorts URLs ───────────────────────────────────────────────
# Three Fireship YouTube Shorts used as the corpus for this POC.
# Fireship (Jeff Delaney) is a popular tech educator with a very distinct style:
# fast-paced, humorous, highly technical — a perfect test subject for style
# extraction because the pipeline should surface a clear, consistent profile.
SAMPLE_VIDEO_URLS: list[str] = [
    "https://www.youtube.com/shorts/yILbNB9QPOA",  # "Every developer ever"
    "https://www.youtube.com/shorts/Tn6-PIqc4UM",  # "100 seconds of Python"
    "https://www.youtube.com/shorts/DC471ZHgMgA",  # "How to be a 10x developer"
]

# ─── Runtime Settings ─────────────────────────────────────────────────────────

# Number of documents to retrieve from ChromaDB during RAG query.
# Since we only have 3 videos, k=3 fetches all of them — giving the LLM
# the full picture when synthesising the master creator profile.
RAG_TOP_K: int = 3

# Delay (seconds) between Groq API calls to respect the free-tier rate limit
# of 30 requests/minute. 2 seconds gives comfortable headroom.
API_CALL_DELAY: float = 2.0

# Maximum number of retries when the LLM returns malformed JSON.
# After this many failures, the pipeline raises an error rather than looping
# forever — a common defensive pattern in production LLM pipelines.
MAX_JSON_RETRIES: int = 2
