"""
local_llm.py — Minimal client for a locally hosted LLM (Ollama)
================================================================
Talks to Ollama's REST API directly with `requests`, so no extra LangChain
packages are needed. Used by the Research Agent for small language tasks
(query generation, cluster labeling) — never for numbers or scores.

Setup (one time):
  1. Install Ollama: https://ollama.com/download
  2. ollama pull qwen2.5:3b       (~2 GB, fits fully in 4 GB VRAM)

Config (.env, optional):
  OLLAMA_HOST  = http://localhost:11434
  OLLAMA_MODEL = qwen2.5:3b

If Ollama is not running, chat_json() raises LocalLLMError and callers
fall back to deterministic, non-LLM behaviour.
"""

from __future__ import annotations

import json
import os

import requests

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:3b"
REQUEST_TIMEOUT = 120  # seconds — first call also loads the model into VRAM


class LocalLLMError(RuntimeError):
    """Raised when the local LLM is unreachable or returns unusable output."""


def chat_json(prompt: str, system: str = "", temperature: float = 0.3,
              max_tokens: int = 400) -> dict:
    """
    Send one prompt to Ollama in JSON mode and return the parsed object.

    Raises:
        LocalLLMError: Ollama not running, model missing, or invalid JSON.
    """
    host = os.getenv("OLLAMA_HOST", DEFAULT_HOST).rstrip("/")
    model = os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        response = requests.post(
            f"{host}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "format": "json",
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        content = response.json()["message"]["content"]
        result = json.loads(content)
    except (requests.RequestException, KeyError, ValueError) as e:
        raise LocalLLMError(f"Local LLM call failed ({model} @ {host}): {e}") from e

    if not isinstance(result, dict):
        raise LocalLLMError(f"Local LLM returned non-object JSON: {result!r}")
    return result
