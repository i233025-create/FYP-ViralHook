"""
test_scripting_agent.py — Unit tests for the Scripting Agent.

No LLM, no ChromaDB, no network: chat_json is replaced by scripted fakes
and the creator context is built from in-memory transcripts.
"""

import json

import numpy as np
import pytest

import pipeline.agents.scripting_agent as sa
from pipeline.local_llm import LocalLLMError
from pipeline.state import ScriptOutput, SceneOutput

TRANSCRIPT = ("You think motivation will save you. It won't. Discipline will. "
              "Why do you wait for the perfect day? Start now. Small steps. Every day.")


SCENE_WORDS = ["discipline", "habits", "focus", "patience", "consistency", "progress"]


def _scenes(hook="Stop waiting for motivation. It is not coming.", words_per_scene=14,
            n=5, caption="Discipline beats motivation"):
    # each scene uses its own word, so scenes never count as repeats
    scenes = [{"timecode": f"0:{i * 6:02d}-0:{(i + 1) * 6:02d}", "clip_idea": "Talking head",
               "caption": caption,
               "voiceover": hook if i == 0 else " ".join([SCENE_WORDS[i]] * words_per_scene) + "."}
              for i in range(n)]
    return {"concept_name": "Discipline", "scenes": scenes}


def _script(**kwargs) -> ScriptOutput:
    return sa._parse_script_response(_scenes(**kwargs), 1, "Contrarian")


JUDGE_ALL_YES = {**{f"q{i}": "yes" for i in range(1, 7)}, "improve": ""}
JUDGE_ALL_NO = {**{f"q{i}": "no" for i in range(1, 7)}, "improve": ""}


def judge(answers):
    """Fake judge: rejects the calibration control hook, answers `answers` otherwise."""
    def fake(prompt, **kwargs):
        return JUDGE_ALL_NO if sa.CONTROL_HOOK in prompt else answers
    return fake


@pytest.fixture(autouse=True)
def fresh_judge_calibration():
    sa._judge_reliability.clear()
    yield
    sa._judge_reliability.clear()


class FakeLLM:
    """Returns queued script responses; answers hook-judge prompts separately."""

    def __init__(self, scripts, judge=None):
        self.scripts = list(scripts)
        self.judge = judge or JUDGE_ALL_YES
        self.prompts = []

    def __call__(self, prompt, **kwargs):
        if "You judge the opening line" in prompt:
            if isinstance(self.judge, Exception):
                raise self.judge
            return JUDGE_ALL_NO if sa.CONTROL_HOOK in prompt else self.judge
        self.prompts.append(prompt)
        response = self.scripts.pop(0) if len(self.scripts) > 1 else self.scripts[0]
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture
def baseline():
    return sa.build_style_baseline([{"transcript": TRANSCRIPT}], {"speech_rate_wpm": 150})


@pytest.fixture
def context(sample_creator_profile, baseline):
    examples = [{"topic": "Discipline", "hook_type": "Contrarian", "hook_text": "",
                 "key_phrases": [], "transcript": TRANSCRIPT}]
    return {"profile": sample_creator_profile, "examples": examples, "retrieval_pool": examples,
            "baseline": baseline}


# ── [1] Context ────────────────────────────────────────────────────────────────

def test_style_features():
    f = sa.style_features("You can do this. Are you ready? Go.")
    assert f["avg_sentence_words"] == pytest.approx(8 / 3)
    assert f["you_ratio"] == pytest.approx(2 / 8)
    assert f["question_ratio"] == pytest.approx(1 / 3)


def test_baseline_without_transcripts_or_audio_uses_defaults():
    b = sa.build_style_baseline([], {})
    assert b["measured_style"] is False
    assert b["wpm"] == sa.DEFAULT_WPM and b["wpm_source"] == "default"
    assert b["word_budget"] == 75


def test_baseline_uses_module2_speech_rate(baseline):
    b = sa.build_style_baseline([], {"speech_rate_wpm": 141.5})
    assert b["wpm"] == 142 and b["wpm_source"] == "module2_audio"
    assert b["word_budget"] == 71
    assert baseline["measured_style"] is True and baseline["transcripts"] == 1


def test_load_multimodal_stats_reads_string_payloads(tmp_path, monkeypatch):
    snapshot = tmp_path / "snap.json"
    snapshot.write_text(json.dumps({"points": [
        {"payload": {"speech_rate_wpm": "141.5", "talking_head_pct": "0.84", "avg_shot_duration": "1.5"}},
        {"payload": {"speech_rate_wpm": "160", "talking_head_pct": "bad"}},
    ]}), encoding="utf-8")
    monkeypatch.setattr(sa, "QDRANT_SNAPSHOT_PATH", snapshot)
    stats = sa.load_multimodal_stats()
    assert stats["speech_rate_wpm"] == pytest.approx(150.75)
    assert stats["talking_head_pct"] == pytest.approx(0.84)


def test_load_creator_examples_without_chromadb(tmp_path, monkeypatch):
    monkeypatch.setattr(sa, "CHROMA_PERSIST_DIR", tmp_path / "missing")
    assert sa.load_creator_examples() == []


# ── [2] Retrieval ──────────────────────────────────────────────────────────────

def test_retrieve_examples_picks_most_similar(monkeypatch):
    examples = [{"topic": t, "transcript": t} for t in ("phones", "discipline", "cooking", "habits")]
    vectors = {"phones": [0, 1, 0], "discipline": [1, 0, 0], "cooking": [0, 0, 1],
               "habits": [0.8, 0.2, 0], "morning discipline": [1, 0, 0]}

    calls = []

    def fake_embed(texts, is_query):
        calls.append(is_query)
        return np.array([vectors[t.split(". ")[0]] for t in texts], dtype=float)

    monkeypatch.setattr(sa, "embed_for_retrieval", fake_embed)
    picked = sa.retrieve_examples(examples, "morning discipline", k=2)
    assert [e["topic"] for e in picked] == ["discipline", "habits"]
    assert sorted(calls) == [False, True]   # e5 needs passage/query prefixes


def test_prepare_context_searches_translated_transcripts(monkeypatch):
    words = " ".join(["word"] * 30)
    rows = [{"topic": "a", "transcript": words, "language": "en"},
            {"topic": "b", "transcript": words, "language": "hi"},
            {"topic": "c", "transcript": "too short", "language": "en"}]
    monkeypatch.setattr(sa, "load_creator_examples", lambda: rows)
    monkeypatch.setattr(sa, "load_multimodal_stats", lambda: {})
    context = sa.prepare_context({"creator_niche": "x"})
    assert [e["topic"] for e in context["examples"]] == ["a"]              # style: spoken English
    assert [e["topic"] for e in context["retrieval_pool"]] == ["a", "b"]   # retrieval: any language


# ── [3] Prompting + generation ─────────────────────────────────────────────────

def test_parse_script_response_defaults_and_drops_empty_scenes():
    raw = {"scenes": [{"voiceover": "Hook line."}, {"voiceover": "  "}, {"voiceover": "..."}, "junk", {"voiceover": "Two."}]}
    script = sa._parse_script_response(raw, 2, "Bold Claim")
    assert script.script_id == 2 and script.hook_type == "Bold Claim"
    assert [s.voiceover for s in script.scenes] == ["Hook line.", "Two."]
    assert script.concept_name == "Untitled Script"


def test_prompts_only_give_creator_context_beyond_baseline(context):
    trend = {"suggested_angle": "Share a personal story.",
             "evidence": [{"title": "Stop comparing yourself"}]}
    args = ("Comparison", "Contrarian", "Hook → Explanation", context["profile"],
            context["baseline"], context["examples"], trend)
    no_history = sa.build_prompt("no_history", *args)
    retrieval = sa.build_prompt("retrieval_only", *args)

    for prompt in (no_history, retrieval):
        assert "Share a personal story." in prompt and "Contrarian hook" in prompt
        assert "popular belief about this topic is wrong" in prompt
        assert "Stop comparing yourself" not in prompt      # titles get copied by small models
    assert "HOW THIS CREATOR ACTUALLY TALKS" not in no_history
    assert "CREATOR PROFILE" not in no_history
    assert "HOW THIS CREATOR ACTUALLY TALKS" in retrieval and TRANSCRIPT[:40] in retrieval
    assert "about 75 spoken words" in retrieval


def test_voiceover_hashtags_and_emoji_are_stripped():
    raw = {"scenes": [{"voiceover": "Live fully today 🌍#life #fyp"}]}
    assert sa._parse_script_response(raw).scenes[0].voiceover == "Live fully today"


def test_skeleton_word_targets_use_creator_wpm(context):
    slow_creator = {**context["baseline"], "wpm": 100}
    args = ("T", "Contrarian", "S", context["profile"], slow_creator, [])
    no_history = sa.build_prompt("no_history", *args)
    retrieval = sa.build_prompt("retrieval_only", *args)
    assert '"timecode": "0:23-0:30"' in retrieval
    # 7-second takeaway slot: generic 150 wpm → 18 words, this creator's 100 wpm → 12
    assert "takeaway: about 18 spoken words" in no_history
    assert "takeaway: about 12 spoken words" in retrieval


def test_regen_prompt_contains_draft_and_feedback(context):
    prompt = sa.build_prompt("full_pipeline", "T", "Contrarian", "S", context["profile"],
                             context["baseline"], [], None, ["Cut about 40 words."], _script())
    assert "YOUR PREVIOUS DRAFT" in prompt and "- Cut about 40 words." in prompt


def test_generate_script_repairs_once(monkeypatch):
    fake = FakeLLM([{"scenes": [{"voiceover": "only one"}]}, _scenes()])
    monkeypatch.setattr(sa, "chat_json", fake)
    script = sa.generate_script("prompt", 1, "Contrarian")
    assert len(script.scenes) == 5
    assert "previous answer was unusable" in fake.prompts[1]


def test_generate_script_gives_up_after_two_bad_answers(monkeypatch):
    monkeypatch.setattr(sa, "chat_json", FakeLLM([{"scenes": []}]))
    with pytest.raises(LocalLLMError):
        sa.generate_script("prompt", 1, "Contrarian")


# ── [4] Evaluation ─────────────────────────────────────────────────────────────

def test_timing_score_and_feedback():
    assert sa.score_timing(75, 75, 150) == (10.0, [])
    score, feedback = sa.score_timing(120, 75, 150)
    assert score == 0.0 and "Cut about 45 words" in feedback[0]
    score, feedback = sa.score_timing(50, 75, 150)
    assert 0 < score < 10 and "Add about 25 words" in feedback[0]


def test_structure_perfect_script():
    assert sa.score_structure(_script()) == (10.0, [])


def test_structure_flags_each_problem():
    script = _script(hook=" ".join(["word"] * 20) + ".", n=4,
                     caption="this caption is far too long for the screen")
    score, feedback = sa.score_structure(script)
    text = " ".join(feedback)
    assert score == pytest.approx(10 * 4 / 8, abs=0.05)   # timecodes, scene length, originality pass
    assert "exactly 5 scenes" in text and "near 0:30" in text
    assert "Hook (scene 1) is 20 words" in text and "Captions must be" in text


def test_structure_rejects_one_word_scene():
    script = _script()
    script.scenes[1] = SceneOutput(timecode="0:06-0:12", clip_idea="", caption="ok", voiceover="Contrarian")
    score, feedback = sa.score_structure(script)
    assert score < 10 and any("Scenes 2 have under 3" in f for f in feedback)


def test_structure_rejects_bad_timecodes():
    script = _script()
    script.scenes[2] = SceneOutput(timecode="soon", clip_idea="", caption="ok", voiceover="x.")
    _, feedback = sa.score_structure(script)
    assert any("Timecodes" in f for f in feedback)


def test_style_not_measured_without_transcripts():
    score, feedback, _ = sa.score_style("Any text.", sa.build_style_baseline([], {}))
    assert score is None and feedback == []


def test_style_matches_creator_own_words(baseline):
    score, feedback, _ = sa.score_style(TRANSCRIPT, baseline)
    assert score == 10.0 and feedback == []


def test_style_feedback_for_long_sentences(baseline):
    long = " ".join(["discipline"] * 30) + ". " + " ".join(["habits"] * 30) + "."
    score, feedback, _ = sa.score_style(long, baseline)
    assert score < 7 and any("shorter sentences" in f for f in feedback)


def test_hook_judge_rubric(monkeypatch):
    monkeypatch.setattr(sa, "chat_json", judge({
        "q1": "yes", "q2": "mostly", "q3": "partly", "q4": "slightly", "q5": "no", "q6": "YES",
        "improve": "Be more specific."}))
    score, feedback = sa.judge_hook("Everyone says rest. They are wrong.", "Contrarian", "Topic")
    assert score == pytest.approx(5.8, abs=0.05)   # (1 + .75 + .5 + .25 + 0 + 1) / 6 × 10
    assert feedback == ["Hook: Be more specific."]


def test_hook_judge_invalid_answer_is_none(monkeypatch):
    monkeypatch.setattr(sa, "chat_json", judge({"q1": "maybe"}))
    assert sa.judge_hook("Everyone says rest. They are wrong.", "Contrarian", "Topic") == (None, [])


def test_one_word_hook_scores_zero_without_asking_judge(monkeypatch):
    def judge_should_not_run(*a, **k):
        raise AssertionError("judge called")
    monkeypatch.setattr(sa, "chat_json", judge_should_not_run)
    score, feedback = sa.judge_hook("Contrarian", "Contrarian", "Topic")
    assert score == 0.0 and "real opening sentence" in feedback[0]


def test_judge_placeholder_echo_is_not_feedback(monkeypatch):
    monkeypatch.setattr(sa, "chat_json", judge({**JUDGE_ALL_NO, "improve": "one sentence on how to improve"}))
    assert sa.judge_hook("Everyone says rest. They are wrong.", "Contrarian", "T")[1] == []


def test_judge_that_praises_control_hook_is_ignored(monkeypatch):
    calls = {"n": 0}

    def flatterer(prompt, **kwargs):
        calls["n"] += 1
        return JUDGE_ALL_YES                     # rates everything 10/10, control included
    monkeypatch.setattr(sa, "chat_json", flatterer)
    assert sa.judge_hook("Everyone says rest. They are wrong.", "Contrarian", "T") == (None, [])
    assert sa.judge_hook("Another decent hook line here.", "Contrarian", "T") == (None, [])
    assert calls["n"] == 1                       # calibrated once, then skipped


def test_copied_phrases_detects_verbatim_runs():
    past = ["You're comparing your level one to someone's level 100. Start slow."]
    script_text = "Listen. You're comparing your level one to someone's level 100 today."
    assert sa.copied_phrases(script_text, past)
    assert sa.copied_phrases("Comparison steals joy, so measure yourself against yesterday.", past) == []


def test_structure_flags_copying_and_repeats():
    script = _script()
    pasted = "You're comparing your level one to someone's level 100. Start slow, stay consistent."
    for i in (2, 3):
        script.scenes[i] = SceneOutput(timecode=script.scenes[i].timecode, clip_idea="", caption="ok",
                                       voiceover=pasted)
    score, feedback = sa.score_structure(script, [pasted])
    text = " ".join(feedback)
    assert "Scenes 4 repeat an earlier scene" in text
    assert "copies the creator's past videos" in text
    assert score == pytest.approx(10 * 6 / 8, abs=0.05)


def test_style_ignores_the_hook(monkeypatch, baseline):
    monkeypatch.setattr(sa, "chat_json", judge(JUDGE_ALL_YES))
    seen = {}
    monkeypatch.setattr(sa, "score_style", lambda text, b: seen.setdefault("text", text) and (8.0, [], {}))
    script = _script(hook="Why do you keep waiting for Monday?")
    sa.evaluate_script(script, baseline, "T")
    assert "Monday" not in seen["text"] and "habits" in seen["text"]


def test_voice_targets_only_with_creator_context(context):
    args = ("T", "Contrarian", "S", context["profile"], context["baseline"], context["examples"])
    assert "VOICE TARGETS" not in sa.build_prompt("no_history", *args)
    retrieval = sa.build_prompt("retrieval_only", *args)
    expected = f"~{context['baseline']['avg_sentence_words']:.0f} words"
    assert "VOICE TARGETS" in retrieval and expected in retrieval


def test_evaluate_overall_skips_unmeasured(monkeypatch):
    monkeypatch.setattr(sa, "chat_json", judge(JUDGE_ALL_YES))
    scores = sa.evaluate_script(_script(), sa.build_style_baseline([], {}), "T")
    assert scores["style_match"] is None
    assert scores["overall"] == pytest.approx((scores["timing"] + scores["structure"] + 10.0) / 3, abs=0.01)


# ── [5] Modes ──────────────────────────────────────────────────────────────────

def _style_is_fine(monkeypatch):
    monkeypatch.setattr(sa, "score_style", lambda text, baseline: (8.0, [], {}))


def test_full_pipeline_rewrites_and_keeps_best(monkeypatch, context):
    _style_is_fine(monkeypatch)   # this test is about timing/copying, not style
    too_long = _scenes(words_per_scene=40)
    good = _scenes()
    fake = FakeLLM([too_long, good])
    monkeypatch.setattr(sa, "chat_json", fake)
    script, meta = sa.run_mode("full_pipeline", "Discipline", context, context["examples"], "Contrarian")
    assert meta["regen_triggered"] is True
    assert len(meta["all_scores"]) == 2
    assert meta["evaluator_scores"]["overall"] == meta["all_scores"][1]["overall"]
    assert "FIX THESE MEASURED PROBLEMS" in fake.prompts[1] and "Cut about" in fake.prompts[1]
    assert len(script.scenes[1].voiceover.split()) == 14


def test_copied_script_is_rewritten_even_with_good_score(monkeypatch, context):
    _style_is_fine(monkeypatch)   # this test is about timing/copying, not style
    copied = _scenes()
    copied["scenes"][2]["voiceover"] = TRANSCRIPT          # pasted from the creator's past video
    fake = FakeLLM([copied, _scenes()])
    monkeypatch.setattr(sa, "chat_json", fake)
    script, meta = sa.run_mode("full_pipeline", "T", context, context["examples"], "Contrarian")
    first, second = meta["all_scores"]
    assert first["original"] is False and second["original"] is True
    assert meta["evaluator_scores"]["original"] is True
    assert TRANSCRIPT not in " ".join(s.voiceover for s in script.scenes)


def test_one_bad_metric_triggers_rewrite_despite_good_average(monkeypatch, context):
    # timing, structure and hook are perfect; only style is far off on the first draft
    drafts = iter([1.0, 9.0])
    monkeypatch.setattr(sa, "score_style", lambda text, baseline: (next(drafts), ["Use shorter sentences."], {}))
    monkeypatch.setattr(sa, "chat_json", FakeLLM([_scenes()]))
    _, meta = sa.run_mode("full_pipeline", "T", context, context["examples"], "Contrarian")
    first = meta["all_scores"][0]
    assert first["overall"] >= sa.REGEN_THRESHOLD and first["style_match"] < sa.MIN_METRIC_SCORE
    assert meta["regen_triggered"] and meta["evaluator_scores"]["style_match"] == 9.0


def test_full_pipeline_stops_after_max_rewrites(monkeypatch, context):
    monkeypatch.setattr(sa, "chat_json", FakeLLM([_scenes(words_per_scene=40)]))
    _, meta = sa.run_mode("full_pipeline", "T", context, context["examples"], "Contrarian")
    assert len(meta["all_scores"]) == 1 + sa.MAX_REGEN_ATTEMPTS


@pytest.mark.parametrize("mode", ["no_history", "retrieval_only"])
def test_ablation_modes_are_scored_but_not_rewritten(monkeypatch, context, mode):
    fake = FakeLLM([_scenes(words_per_scene=40)])
    monkeypatch.setattr(sa, "chat_json", fake)
    _, meta = sa.run_mode(mode, "T", context, context["examples"], "Contrarian")
    assert meta["regen_triggered"] is False and len(fake.prompts) == 1
    assert meta["evaluator_scores"]["overall"] is not None
    assert meta["examples_used"] == (0 if mode == "no_history" else 1)


def test_variant_hooks_dedupes_and_tops_up():
    assert sa.variant_hooks({"signature_hooks": ["Contrarian", "Bold Claim"]}) == \
        ["Contrarian", "Bold Claim", "Curiosity Gap"]


def test_unknown_signature_hooks_are_ignored():
    profile = {"signature_hooks": ["Listen! Université Chandu, VN", "curiosity gap"]}
    assert sa.variant_hooks(profile) == ["Curiosity Gap", "Bold Claim", "Contrarian"]
    assert sa._extract_style_params(profile)["hook_type"] == "Curiosity Gap"
    assert sa._extract_style_params({"signature_hooks": ["???"]})["hook_type"] == "Bold Claim"


def test_generate_variants_skips_failed_variant(monkeypatch, context):
    monkeypatch.setattr(sa, "prepare_context", lambda profile=None: context)
    calls = {"n": 0}

    def flaky(prompt, **kwargs):
        if "You judge the opening line" in prompt:
            return JUDGE_ALL_YES
        calls["n"] += 1
        if "a Bold Claim hook" in prompt:
            raise LocalLLMError("model crashed")
        return _scenes()

    monkeypatch.setattr(sa, "chat_json", flaky)
    results = sa.generate_variants("Discipline")
    assert [m["hook_type"] for _, m in results] == ["Contrarian", "Curiosity Gap"]
    assert [s.script_id for s, _ in results] == [1, 3]


def test_generate_variants_raises_when_all_fail(monkeypatch, context):
    monkeypatch.setattr(sa, "prepare_context", lambda profile=None: context)
    monkeypatch.setattr(sa, "chat_json", FakeLLM([LocalLLMError("offline")]))
    with pytest.raises(LocalLLMError):
        sa.generate_variants("Discipline")


def test_node_requires_topic():
    out = sa.scripting_agent({"research_output": {}})
    assert out["scripting_output"] is None and "No topic" in out["scripting_error"]


def test_node_reports_llm_failure_without_crashing(monkeypatch, context):
    monkeypatch.setattr(sa, "prepare_context", lambda profile=None: context)
    monkeypatch.setattr(sa, "chat_json", FakeLLM([LocalLLMError("offline")]))
    out = sa.scripting_agent({"research_output": {"topic": "Discipline"}})
    assert out["scripting_output"] is None and "offline" in out["scripting_error"]


def test_node_returns_variants_and_best_final(monkeypatch, context):
    monkeypatch.setattr(sa, "prepare_context", lambda profile=None: context)
    monkeypatch.setattr(sa, "chat_json", FakeLLM([_scenes()]))
    out = sa.scripting_agent({"research_output": {"topic": "Discipline"}})
    assert len(out["scripting_output"].scripts) == 3
    assert out["scripting_output"].final_script is not None
