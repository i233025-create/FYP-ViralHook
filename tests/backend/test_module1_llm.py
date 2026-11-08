"""
test_module1_llm.py — Module 1 profiling runs on the shared LLM client.

No Groq, no Ollama: the shared client is replaced by a fake, so these tests
only check that Module 1's chains build prompts, parse JSON and retry the
way the old prompt | ChatGroq | JsonOutputParser chains did.
"""

import pytest

import module1_style_extraction.llm_chain as llm_chain
from module1_style_extraction.video_profiler import create_video_profiler_chain, extract_video_profile
from module1_style_extraction.creator_profiler import create_creator_profile_chain
from pipeline.local_llm import LocalLLMError

PROFILE = {
    "topic": "Stop comparing yourself", "hook_text": "You'll never be like them.",
    "hook_type": "Contrarian", "structure": "Hook → Explanation", "tone": "Inspirational",
    "pacing": "Fast-paced", "key_phrases": "trust the process", "transcript_summary": "...",
}


def test_chain_sends_filled_prompt_without_chat_prefix(monkeypatch):
    sent = {}

    def fake(prompt, **kwargs):
        sent["prompt"], sent["kwargs"] = prompt, kwargs
        return dict(PROFILE)
    monkeypatch.setattr(llm_chain, "chat_json", fake)

    result = create_video_profiler_chain().invoke({"transcript": "You'll never be like them.",
                                                   "video_url": "video.mp4"})
    assert result["topic"] == "Stop comparing yourself"
    assert "You'll never be like them." in sent["prompt"] and "video.mp4" in sent["prompt"]
    assert not sent["prompt"].startswith("Human:")
    assert sent["kwargs"] == {"temperature": 0.3, "max_tokens": 1024}


def test_creator_chain_uses_its_own_settings(monkeypatch):
    seen = {}
    monkeypatch.setattr(llm_chain, "chat_json", lambda prompt, **kw: seen.update(kw) or {"ok": 1})
    create_creator_profile_chain().invoke({"context": "Video 1: ..."})
    assert seen == {"temperature": 0.4, "max_tokens": 2048}


def test_extract_profile_retries_invalid_llm_json(monkeypatch):
    answers = iter([LocalLLMError("invalid JSON from small model"), dict(PROFILE)])

    def flaky(prompt, **kwargs):
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer
    monkeypatch.setattr(llm_chain, "chat_json", flaky)
    monkeypatch.setattr("module1_style_extraction.video_profiler.time.sleep", lambda s: None)

    profile = extract_video_profile(create_video_profiler_chain(), "Some transcript.", "v.mp4")
    assert profile["key_phrases"] == ["trust the process"]   # string normalised to list
    assert profile["video_url"] == "v.mp4"


def test_provider_label(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:1.5b")
    assert llm_chain.provider_label() == "ollama (qwen2.5:1.5b)"
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    assert llm_chain.provider_label().startswith("groq")


@pytest.mark.parametrize("example,usable", [
    ({"transcript": " ".join(["word"] * 25), "language": "en"}, True),
    ({"transcript": " ".join(["word"] * 25), "language": ""}, True),        # unknown: kept
    ({"transcript": " ".join(["word"] * 25), "language": "hi"}, False),     # translated
    ({"transcript": "Road towards Pavanji", "language": "en"}, False),     # too short
])
def test_usable_for_style(example, usable):
    from pipeline.agents.scripting_agent import usable_for_style
    assert usable_for_style(example) is usable


def test_baseline_confidence_depends_on_word_count():
    from pipeline.agents.scripting_agent import build_style_baseline
    short = build_style_baseline([{"transcript": "You can do it. Start now."}], {})
    long = build_style_baseline([{"transcript": "You can do it. Start now. " * 40}], {})
    assert short["low_confidence"] is True and short["baseline_words"] == 6
    assert long["low_confidence"] is False
