# Experiment E4 — Urdu / Urdu–English transcripts for creator STYLE

**Question.** E1 settled retrieval: transcribe in English (`language="en"`) and
search with multilingual-e5-small. But an English transcript is a translation —
a Pakistani creator's own words, catchphrases and Urdu–English mix are gone, and
those are what the Scripting Agent should imitate. Which local pipeline gives the
most faithful **Roman Urdu** transcript (Urdu in Latin letters, English words in
English), and what style does it reveal per creator?

**Design decision already taken (not tested here):** two transcripts per reel.
English → retrieval (E1). Roman Urdu → style (shown to the LLM + measured).
Retrieval returns a reel ID; the style text of that reel is looked up.

## Variants

| Name | Whisper | Then |
|---|---|---|
| `small` | small, `language="ur"` (already in `transcripts_small_ur.json`, v1 creators only) | LLM romanize |
| `turbo` | large-v3-turbo, `language="ur"` | LLM romanize |
| `prompt` | large-v3-turbo, `language="en"` + Roman Urdu `--initial-prompt` | nothing (Whisper writes Latin directly, if the trick works) |

Romanization = `pipeline/urdu_style.romanize`: local Ollama model, transliterate
not translate, English words in English, the English transcript as a hint for
which words were English. Try a 7B+ model (`qwen2.5:7b` / `qwen2.5:14b`); the
pipeline default `qwen2.5:3b` is weak at Urdu.

## Metrics

- **WER** against a human-corrected Roman Urdu reference (10–15 reels), after
  spelling normalisation (`hai/hay/he`, `nahi/nahin/nai`, …). Roman Urdu has no
  standard spelling, so plain WER would punish spelling, not errors.
- **English-share error** — the code-switch ratio is a style feature the
  Scripting Agent targets, so it must survive transcription.
- Style cards (descriptive): English share overall / hook / body / end,
  catchphrases distinctive vs the other creators, openers, closers, how the
  viewer is addressed, caption (written) style.

## Run (GPU lab PC, from `experiments/rag_e4/`)

The .mp4 files must be in `../rag_e1/data/<creator>/` (see `../rag_e1/HANDOFF.md`).

```bash
# 1. Transcribe (faster-whisper; reuses E1's script)
cd ../rag_e1
python prepare_data.py --creators "Hamza Bhatti v2" "Rabika Tahir v2" "Tech Wisdom v2" \
    --model large-v3-turbo --language ur --out transcripts_turbo_ur.json
python prepare_data.py --creators "Hamza Bhatti v2" "Rabika Tahir v2" "Tech Wisdom v2" \
    --model large-v3-turbo --language en --out transcripts_turbo_prompt.json \
    --initial-prompt "Dosto aaj hum baat karenge. Yeh video bohat interesting hai, so let's start."
cd ../rag_e4

# 2. Urdu script → Roman Urdu (Ollama running, model pulled)
python romanize_transcripts.py --urdu transcripts_turbo_ur.json --llm qwen2.5:14b --limit 3   # look first
python romanize_transcripts.py --urdu transcripts_turbo_ur.json --llm qwen2.5:14b

# 3. Style cards
python style_cards.py --roman transcripts_turbo_roman.json --tag turbo

# 4. Accuracy: build the sheet, correct `reference` while listening, score
python asr_check.py sheet --variants turbo=transcripts_turbo_roman.json \
    prompt=transcripts_turbo_prompt.json --per-creator 4
python asr_check.py score --tag v1

python -m pytest tests -q
```

Outputs: `results/e4_asr_<tag>.md` (numbers only) and
`results/e4_style_cards_<tag>.md` (quotes short catchphrases — check before
committing). Transcripts and the reference sheet stay in the git-ignored data folder.

## In the product

Module 1 does the same for every uploaded video whose spoken language Whisper
detects as `ur`/`hi`/`pa`: a second Whisper pass (`language="ur"`), then
`romanize`, stored as `transcript_ur` / `transcript_roman` in ChromaDB metadata.
Settings in `module1_style_extraction/config.py` (`NATIVE_TRANSCRIPT`,
`NATIVE_WHISPER_MODEL`, `ROMANIZE_MODEL`). The Scripting Agent then shows the
Roman transcripts as examples, adds the style card to the prompt, and its
style_match metric includes closeness to the creator's English share.
Module 1 uses openai-whisper (no turbo in the pinned version), so the product
uses `large-v3` on GPU / `medium` on CPU; E4's result decides whether that changes.
