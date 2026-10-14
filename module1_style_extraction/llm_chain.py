"""
llm_chain.py — Module 1 LCEL chains backed by the project's shared LLM client
===============================================================================
Module 1 keeps its LCEL shape (prompt | llm), but the "llm" step is the
shared JSON-mode client in pipeline/local_llm.py, so Module 1 follows the
same "no API LLM by default" rule as the agents:

  LLM_PROVIDER=ollama (default) → local model (OLLAMA_MODEL), no API key
  LLM_PROVIDER=groq             → Groq, needs GROQ_API_KEY

Each chain accepts the prompt variables as a dict and returns a parsed
JSON dict, exactly like the old prompt | ChatGroq | JsonOutputParser chain.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda

sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.local_llm import LocalLLMError, chat_json  # noqa: E402,F401  (re-exported)


def provider_label() -> str:
    """Human-readable 'provider (model)' for console output."""
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    if provider == "groq":
        return f"groq ({os.getenv('GROQ_MODEL', 'openai/gpt-oss-20b')})"
    return f"ollama ({os.getenv('OLLAMA_MODEL', 'qwen2.5:3b')})"


def json_chain(template: str, temperature: float, max_tokens: int) -> Runnable:
    """prompt | shared LLM (JSON mode) → dict."""
    prompt = ChatPromptTemplate.from_template(template)
    llm = RunnableLambda(lambda value: chat_json(
        value.to_messages()[-1].content, temperature=temperature, max_tokens=max_tokens))
    return prompt | llm
