"""
test_local_llm.py — LLM client behaviour without a real LLM (requests is faked).
"""

import json

import pytest

import pipeline.local_llm as llm


class FakeResponse:
    def __init__(self, status, payload=None, text="", headers=None):
        self.status_code = status
        self.ok = status < 400
        self._payload = payload
        self.text = text or json.dumps(payload or {})
        self.headers = headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if not self.ok:
            raise llm.requests.HTTPError(str(self.status_code))


def _groq_ok(content):
    return FakeResponse(200, {"choices": [{"message": {"content": content}}]})


@pytest.fixture
def groq_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)


@pytest.mark.parametrize("text,expected", [
    ("Please try again in 2.01s. Need more", 2.01),
    ("Please try again in 750ms.", 0.75),
    ("no hint here", None),
])
def test_seconds_in(text, expected):
    assert llm._seconds_in(text) == expected


def test_groq_retries_on_rate_limit(monkeypatch, groq_env):
    responses = iter([FakeResponse(429, text="Rate limit. Please try again in 750ms."),
                      _groq_ok('{"ok": true}')])
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: next(responses))
    assert llm.chat_json("Return JSON") == {"ok": True}


def test_groq_error_body_is_reported(monkeypatch, groq_env):
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: FakeResponse(
        400, text='{"error": {"code": "json_validate_failed"}}'))
    with pytest.raises(llm.LocalLLMError, match="json_validate_failed"):
        llm.chat_json("Return JSON")


def test_gpt_oss_gets_low_reasoning_effort(monkeypatch, groq_env):
    sent = {}

    def capture(url, headers=None, json=None, timeout=None):
        sent.update(json)
        return _groq_ok('{"ok": 1}')
    monkeypatch.setattr(llm.requests, "post", capture)
    llm.chat_json("Return JSON", model="openai/gpt-oss-20b")
    assert sent["reasoning_effort"] == "low"


def test_groq_without_key_fails_clearly(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(llm.LocalLLMError, match="GROQ_API_KEY"):
        llm.chat_json("x")


def test_ollama_non_object_json_rejected(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: FakeResponse(
        200, {"message": {"content": "[1, 2]"}}))
    with pytest.raises(llm.LocalLLMError, match="non-object"):
        llm.chat_json("x")
