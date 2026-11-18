"""
test_urdu_style.py — Roman Urdu style card, romanization and their use in the
Scripting Agent. No LLM, no Whisper: the LLM is a fake callable.
"""

import pytest

import pipeline.agents.scripting_agent as sa
from pipeline import urdu_style as us

ROMAN = [
    "Dosto aaj hum try kar rahe hain spicy beef tikka. Kharcha hogaya ustaad! Bas yahi tha aaj ka.",
    "Dosto aaj hum Pindi mein hain. Yeh shop bohat famous hai. Kharcha hogaya ustaad. Bas yahi tha aaj ka.",
    "Dosto aaj ka topic hai visa. Aap log comment karo. Bas yahi tha aaj ka.",
]
ENGLISH = [
    "Friends today we are trying spicy beef tikka. It was expensive man. That was it for today.",
    "Friends today we are in Pindi. This shop is very famous. Expensive man. That is it.",
    "Friends today's topic is visa. You people comment. That is all for today.",
]


# ── Script + lexicon ───────────────────────────────────────────────────────────

def test_arabic_script_share():
    assert us.arabic_script_share("aaj hum shop par hain") == 0.0
    assert us.arabic_script_share("آج ہم شوپ پر ہیں") == 1.0
    assert 0 < us.arabic_script_share("آج ہم shop پر ہیں") < 1


def test_english_ratio_with_builtin_lexicon():
    assert us.english_ratio("aaj hum shop par hain") == pytest.approx(1 / 5)
    assert us.english_ratio("") == 0.0
    assert us.english_ratio("2024 mein") == 0.0   # digits ignored


def test_english_words_count_as_english_even_if_translation_dropped_them():
    # Whisper's translation paraphrases: "food", "video" are often not in it
    roman = ["yeh food video bohat famous hai karhai pulao tikka"]
    english = ["this is a very well known clip of a dish"]
    lexicon = us.build_lexicon(roman, english)
    assert us.english_ratio(roman[0], lexicon) == pytest.approx(3 / 9)   # food video famous
    assert not us.is_english("tikka", lexicon) and us.is_english("restaurant", lexicon)


def test_short_english_looking_words_can_be_urdu():
    lexicon = us.build_lexicon(["meri bat suno aaj rat ko"], ["listen to me tonight"])
    assert "bat" in lexicon and "rat" in lexicon            # baat, raat
    assert us.is_english("bat") and not us.is_english("bat", lexicon)


def test_lexicon_learns_urdu_words_missing_from_translation():
    lexicon = us.build_lexicon(ROMAN, ENGLISH)
    assert "kharcha" in lexicon and "ustaad" in lexicon      # not in the English translation
    assert "shop" not in lexicon and "spicy" not in lexicon   # spoken in English


def test_segment_ratios_split_hook_body_end():
    text = " ".join(["shop"] * 12 + ["hai"] * 20 + ["video"] * 12)
    parts = us.segment_english_ratios(text)
    assert parts == {"hook": 1.0, "body": 0.0, "end": 1.0}


# ── Style card ─────────────────────────────────────────────────────────────────

def test_catchphrases_come_out_whole():
    phrases = [c["phrase"] for c in us.catchphrases(ROMAN)]
    assert phrases[0] == "bas yahi tha aaj"       # not "... aaj ka": a phrase does not end on "ka"
    assert "yahi tha aaj" not in phrases        # fragment of a longer phrase in as many reels


def test_catchphrases_drop_what_other_creators_also_say():
    background = ["dosto aaj hum kahin ja rahe hain", "dosto aaj hum khana bana rahe hain"]
    phrases = [c["phrase"] for c in us.catchphrases(ROMAN, background)]
    assert "dosto aaj hum" not in phrases and "bas yahi tha aaj" in phrases


def test_catchphrases_drop_fragments_and_grammar():
    texts = [f"is ki first bite mein kaho ge wah yaar ko to bhai {w} kar rahay hain" for w in ("tikka", "pulao")]
    phrases = [c["phrase"] for c in us.catchphrases(texts)]
    assert not any(p.split()[0] in ("ko", "mein") or p.split()[-1] in ("ko", "mein") for p in phrases)
    assert "kar rahay hain" not in phrases                        # grammar only
    assert "first bite mein kaho ge wah yaar" in phrases


def test_catchphrase_comes_with_how_it_is_said():
    card = us.style_card(ROMAN, ENGLISH)
    example = card["catchphrases"][0]["example"]
    assert example == "... beef tikka kharcha hogaya ustaad bas yahi ..."
    assert len(us.tokens(example)) < sa.COPY_NGRAM        # copying the example is not copying a video
    assert f'(as in: "{example}")' in us.card_prompt(card)


def test_catchphrase_ending_on_misheard_stub_is_dropped():
    texts = ["mujhe comments mein batao ke ar team kaun si", "aur comments mein batao ke ar ee o team"]
    assert "batao ke ar" not in [c["phrase"] for c in us.catchphrases(texts)]


def test_strip_opener_tolerates_spelling():
    opener = "bhati armi pakhir raglay"
    assert us.strip_opener("Bhati Armee pakhir raglay, ye shop 100 saal purani hai", opener) \
        == "ye shop 100 saal purani hai"
    assert us.strip_opener("ye shop 100 saal purani hai", opener) == "ye shop 100 saal purani hai"
    assert us.strip_opener("bhati armi pakhir raglay", opener) == ""


def test_hook_is_judged_without_the_greeting(monkeypatch):
    seen = []
    monkeypatch.setattr(sa, "judge_hook", lambda hook, *a: (seen.append(hook) or 7.0, []))
    baseline = sa.build_style_baseline(_examples(), {})
    baseline["urdu_style"]["openers"] = [{"phrase": "dosto aaj", "reels": 3}]
    script = sa.ScriptOutput(script_id=1, concept_name="x", hook_type="Bold Claim", scenes=[
        sa.SceneOutput(timecode=f"0:{a:02d}-0:{b:02d}", clip_idea="c", caption="c",
                       voiceover="Dosto aaj, yeh Lahore ki sab se purani nihari hai" if a == 0
                       else "yahan log subah se line mein khade hote hain")
        for a, b, _ in sa.SCENE_SLOTS])
    result = sa.evaluate_script(script, baseline, "nihari")
    assert seen == ["yeh Lahore ki sab se purani nihari hai"]
    assert not any("Hook (scene 1)" in f for f in result["feedback"])


def test_card_prompt_warns_phrases_may_be_misspelled():
    assert us.ASR_SPELLING_NOTE in us.card_prompt(us.style_card(ROMAN, ENGLISH))
    card = us.style_card(ROMAN, ENGLISH)
    card.update(catchphrases=[], openers=[])
    assert us.ASR_SPELLING_NOTE not in us.card_prompt(card)


def test_output_spec_puts_greeting_before_hook():
    spec = sa._output_spec(140, "bhati armi pakhir raglay")
    assert 'the greeting "bhati armi pakhir raglay", then a hook sentence' in spec


def test_catchphrases_need_two_reels():
    assert us.catchphrases(ROMAN[:1]) == []


def test_style_card_fields():
    card = us.style_card(ROMAN, ENGLISH, captions=["Ye hai Pindi #pindi 🇵🇰 🔥"])
    assert card["reels"] == 3
    assert 0 < card["english_ratio"] < 0.5
    assert card["openers"][0] == {"phrase": "dosto aaj", "reels": 3}
    assert card["closers"][0] == {"phrase": "bas yahi tha aaj ka", "reels": 3}
    assert [c["phrase"] for c in card["catchphrases"]] == ["kharcha hogaya ustaad"]   # sign-off excluded
    assert "dosto" in card["address"]
    assert card["written"]["hashtags_per_caption"] == 1.0
    assert card["written"]["emoji_per_caption"] >= 1


def test_opener_survives_asr_spelling_and_leading_words():
    tail = " yeh dish bohat mashhoor hai is ka gosht naram hai aur log door door se aate hain"
    texts = ["bhati armi pakhir raglay aaj hum tikka try kar rahay hain" + tail,
             "haan bhati armi bakhair aag lay yeh hai peshawar ka nashta" + tail.replace("dish", "cheez"),
             "karhai wala pulao yeh kya hai",
             "bhati armi pakhra raghle hum halim try kar rahay hain" + tail.replace("gosht", "chawal")]
    card = us.style_card(texts)
    assert card["openers"][0] == {"phrase": "bhati armi", "reels": 3}
    assert card["catchphrases"]
    assert not any("bhati" in c["phrase"] for c in card["catchphrases"])   # not a mid-script phrase


def test_greeting_split_by_asr_is_joined():
    texts = ["bhati armi pakhir raglay aaj hum tikka khayenge",
             "bhati armi pakhir raglay yeh hai peshawar",
             "bhati armi bakhair aag lay nashta karte hain",
             "karhai wala pulao yeh kya hai",
             "bhati armi pakhir raglay hum halim try karte hain"]
    assert us.style_card(texts)["openers"][0] == {"phrase": "bhati armi pakhir raglay", "reels": 3}


def test_rare_edge_phrase_is_not_a_sign_off():
    # "let me" closes 2 of 12 reels: below 20%, not their sign-off
    texts = [f"aaj hum jagah {i} par hain comment below and let me" for i in range(2)]
    texts += [f"aaj ka khana number {i} bohat acha tha yaar" for i in range(10)]
    card = us.style_card(texts)
    assert not any(c["phrase"].endswith("let me") for c in card["closers"])


def test_unpunctuated_transcripts_have_no_sentence_length():
    card = us.style_card([" ".join(["lafz"] * 60), " ".join(["lafz"] * 50)])
    assert card["avg_sentence_words"] is None


def test_style_card_empty():
    assert us.style_card([]) == {"reels": 0}
    assert us.card_prompt({"reels": 0}) == ""


def test_card_prompt_mentions_mix_and_phrases():
    prompt = us.card_prompt(us.style_card(ROMAN, ENGLISH))
    assert "Roman Urdu" in prompt and "English words" in prompt
    assert '"kharcha hogaya ustaad"' in prompt and "clip_idea in plain English" in prompt
    assert 'OPENER: they often start a reel with the greeting "dosto aaj ..."' in prompt
    assert 'SIGN-OFF: they often end with "... bas yahi tha aaj ka"' in prompt


# ── Romanization ───────────────────────────────────────────────────────────────

def test_chunks_cut_unpunctuated_text():
    chunks = us._chunks(" ".join(["لفظ"] * 250), size=90)
    assert [len(c.split()) for c in chunks] == [90, 90, 70]


def test_chunks_merge_short_tail():
    # a short last chunk alone makes the LLM drift back into Urdu script
    chunks = us._chunks(" ".join(["لفظ"] * 200), size=90)
    assert [len(c.split()) for c in chunks] == [90, 110]


def test_romanize_calls_llm_per_chunk_with_english_hint():
    prompts = []

    def fake(prompt, **kwargs):
        prompts.append(prompt)
        return {"roman": "aaj hum shop par hain."}

    out = us.romanize(" ".join(["لفظ"] * 150), "today we are at the shop", chat=fake)
    assert len(prompts) == 2 and "today we are at the shop" in prompts[0]
    assert out == "aaj hum shop par hain. aaj hum shop par hain."


def test_romanize_retry_raises_temperature():
    temps = []

    def fake(prompt, temperature, **kwargs):
        temps.append(temperature)
        return {"roman": "آج ہم" if len(temps) == 1 else "aaj hum"}

    assert us.romanize("آج ہم", chat=fake) == "aaj hum"
    assert temps[0] < temps[1]


def test_plain_latin_strips_diacritics():
    assert us.plain_latin("mōṭa chāvl bẖains ɪnjdɪnɪnt") == "mota chavl bhains injdinint"


def test_romanize_returns_plain_latin():
    out = us.romanize("موٹا چاول", chat=lambda prompt, **kw: {"roman": "mōṭa chāvl"})
    assert out == "mota chavl"


def test_romanize_skips_latin_text_and_empty():
    def fail(prompt, **kwargs):
        raise AssertionError("LLM must not be called")
    assert us.romanize("aaj hum shop par hain", chat=fail) == "aaj hum shop par hain"
    assert us.romanize("", chat=fail) == ""


def test_romanize_retries_then_fails_on_urdu_script_answer():
    calls = []

    def stubborn(prompt, **kwargs):
        calls.append(1)
        return {"roman": "آج ہم شوپ پر ہیں"}

    with pytest.raises(us.RomanizeError):
        us.romanize("آج ہم شوپ پر ہیں", chat=stubborn, retries=1)
    assert len(calls) == 2


def test_romanize_wraps_llm_errors():
    def down(prompt, **kwargs):
        raise RuntimeError("connection refused")
    with pytest.raises(us.RomanizeError):
        us.romanize("آج ہم شوپ پر ہیں", chat=down, retries=0)


# ── Scripting Agent integration ────────────────────────────────────────────────

def _examples():
    return [{"topic": f"t{i}", "transcript": e, "language": "hi", "transcript_roman": r * 3}
            for i, (r, e) in enumerate(zip(ROMAN, ENGLISH))]


def test_roman_transcripts_count_as_creator_style():
    roman_hi = {"transcript": " ".join(["word"] * 30), "language": "hi",
                "transcript_roman": " ".join(["lafz"] * 30)}
    translated_only = {"transcript": " ".join(["word"] * 30), "language": "hi"}
    assert sa.usable_for_style(roman_hi) is True
    assert sa.usable_for_style(translated_only) is False


def test_baseline_carries_urdu_style_card():
    baseline = sa.build_style_baseline(_examples(), {})
    assert baseline["roman_transcripts"] == 3
    assert baseline["urdu_style"]["catchphrases"]
    assert 0 < baseline["english_ratio"] < 0.5
    assert "kharcha" in baseline["_lexicon"]


def test_baseline_sentences_from_english_when_roman_unpunctuated():
    examples = [{"transcript": "Today we eat. Is it good? Yes it is.", "language": "hi",
                 "transcript_roman": "aaj hum khate hain " * 15} for _ in range(2)]
    baseline = sa.build_style_baseline(examples, {})
    assert baseline["sentence_source"] == "english_transcript"
    assert baseline["avg_sentence_words"] < 5 and baseline["question_ratio"] == pytest.approx(1 / 3)


def test_baseline_without_roman_has_no_card():
    baseline = sa.build_style_baseline([{"transcript": "You can do it. Start now."}], {})
    assert baseline["roman_transcripts"] == 0 and "urdu_style" not in baseline


def test_prompt_shows_roman_examples_and_language_rule(sample_creator_profile):
    examples = _examples()
    baseline = sa.build_style_baseline(examples, {})
    prompt = sa.build_prompt("retrieval_only", "Lahore street food", "Bold Claim", "Hook → Story",
                             sample_creator_profile, baseline, examples)
    assert "Kharcha hogaya ustaad" in prompt          # creator's own words, not the translation
    assert "It was expensive man" not in prompt
    assert "LANGUAGE:" in prompt


def test_style_score_penalises_wrong_language_mix():
    baseline = sa.build_style_baseline(_examples(), {})
    urdu_like = "Dosto aaj hum Lahore mein hain. Yeh khana bohat acha hai. Bas yahi tha aaj ka."
    english = "Friends today we are in Lahore. This food is very good. That was it for today."
    good, good_fb, good_f = sa.score_style(urdu_like, baseline)
    bad, bad_fb, bad_f = sa.score_style(english, baseline)
    assert good_f["english_ratio"] < bad_f["english_ratio"]
    assert good > bad
    assert any("Use more Urdu" in f for f in bad_fb)


def test_catchphrases_are_not_copying():
    phrase = "kharcha hogaya ustaad bas yahi tha aaj ka"
    past = ["Dosto Pindi mein hain kharcha hogaya ustaad bas yahi tha aaj ka"]
    text = f"Naya video hai {phrase} dosto"
    assert sa.copied_phrases(text, past)                      # verbatim 8-word run
    assert sa.copied_phrases(text, past, allowed=[phrase]) == []


def test_scene_ends_a_sentence_without_full_stop():
    assert sa._end_sentence("aaj hum yahan hain") == "aaj hum yahan hain."
    assert sa._end_sentence("kya hai?") == "kya hai?" and sa._end_sentence("") == ""
