"""
local_llm.py — Minimal JSON-mode LLM client (local Ollama by default)
======================================================================
Talks to the LLM over plain HTTP with `requests`, so no extra LangChain
packages are needed. Used by the Research Agent (queries, cluster labels)
and the Scripting Agent (script writing, hook judging).

Providers (LLM_PROVIDER in .env):
  ollama (default) — local model, no API, no key.
      Install https://ollama.com, then:  ollama pull qwen2.5:3b
  groq             — optional cloud fallback if the supervisor allows it.
      Needs GROQ_API_KEY. Uses Groq's OpenAI-compatible endpoint.

Config (.env, all optional):
  LLM_PROVIDER = ollama | groq
  OLLAMA_HOST  = http://localhost:11434
  OLLAMA_MODEL = qwen2.5:3b
  GROQ_MODEL   = openai/gpt-oss-20b

Callers may pass `model=` to override the provider default for one task
(e.g. a bigger model for scripting). It must be a model of that provider.

If the LLM is unreachable or returns unusable output, chat_json() raises
LocalLLMError and callers fall back or report the error.
"""

from __future__ import annotations

import json
import os
import re
import time

import requests

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "qwen2.5:3b"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
REQUEST_TIMEOUT = 600  # seconds — a full script on a CPU-only laptop can take minutes
GROQ_RATE_LIMIT_RETRIES = 3   # 429 retries, waiting as long as Groq asks


class LocalLLMError(RuntimeError):
    """Raised when the LLM is unreachable or returns unusable output."""


def _messages(prompt: str, system: str) -> list[dict]:
    messages = [{"role": "system", "content": system}] if system else []
    messages.append({"role": "user", "content": prompt})
    return messages


def _ollama(prompt: str, system: str, temperature: float, max_tokens: int, model: str | None) -> str:
    host = os.getenv("OLLAMA_HOST", DEFAULT_HOST).rstrip("/")
    model = model or os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
    response = requests.post(
        f"{host}/api/chat",
        json={
            "model": model,
            "messages": _messages(prompt, system),
            "format": "json",
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()["message"]["content"]


def _seconds_in(text: str) -> float | None:
    """Parse 'try again in 2.01s' / '750ms' from a Groq rate-limit message."""
    match = re.search(r"try again in ([\d.]+)(ms|s)", text)
    if not match:
        return None
    value = float(match.group(1))
    return value / 1000 if match.group(2) == "ms" else value


def _groq(prompt: str, system: str, temperature: float, max_tokens: int, model: str | None) -> str:
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        raise LocalLLMError("LLM_PROVIDER=groq but GROQ_API_KEY is not set")
    model = model or os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)
    body = {
        "model": model,
        "messages": _messages(prompt, system),
        "response_format": {"type": "json_object"},
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if "gpt-oss" in model:
        # Reasoning models otherwise spend the whole token budget thinking
        # and return empty JSON (json_validate_failed).
        body["reasoning_effort"] = "low"
    for attempt in range(GROQ_RATE_LIMIT_RETRIES + 1):
        response = requests.post(GROQ_URL, headers={"Authorization": f"Bearer {api_key}"},
                                 json=body, timeout=REQUEST_TIMEOUT)
        if response.status_code != 429 or attempt == GROQ_RATE_LIMIT_RETRIES:
            break
        # Free tier is ~8k tokens/minute; Groq says how long to wait
        wait = float(response.headers.get("retry-after") or 0) or _seconds_in(response.text) or 5.0
        time.sleep(min(wait + 0.5, 60.0))
    if not response.ok:   # Groq explains 4xx errors in the body (e.g. json_validate_failed)
        raise LocalLLMError(f"Groq HTTP {response.status_code}: {response.text[:300]}")
    return response.json()["choices"][0]["message"]["content"]


def chat_json(prompt: str, system: str = "", temperature: float = 0.3,
              max_tokens: int = 400, model: str | None = None) -> dict:
    """
    Send one prompt in JSON mode and return the parsed object.

    Raises:
        LocalLLMError: LLM not running, model missing, or invalid JSON.
    """
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    call = _groq if provider == "groq" else _ollama
    try:
        content = call(prompt, system, temperature, max_tokens, model)
        result = json.loads(content)
    except LocalLLMError:
        raise
    except (requests.RequestException, KeyError, IndexError, ValueError) as e:
        raise LocalLLMError(f"LLM call failed ({provider}): {e}") from e

    if not isinstance(result, dict):
        raise LocalLLMError(f"LLM returned non-object JSON: {result!r}")
    return result
