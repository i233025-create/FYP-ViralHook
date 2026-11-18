# RAG experiments — handoff (2026-11-18)

Context for continuing E1 v2 on the GPU lab PC. Read this first, then
`README.md` (section "E1 v2"), `REPORT.md` and `results/e1_summary_v2_caption.md`.

## Project rules
- Only local / self-hosted models. No hosted APIs (no Groq, OpenAI, etc.).
- The user commits and pushes themselves. Give them git commands, don't run them.
  Branches: feature/* → dev → main.
- Reply in the user's language (English → English, Roman Urdu → Roman Urdu).
- The supervisor wants research-backed RAG decisions. Personalisation means
  voice + script style + visual style + creator assets.

## Done (merged to main, PR #2)
- E1 v1: Whisper `--language en` beats auto-detect, because auto-detect writes
  Pakistani Urdu–English in Hindi script. Picked multilingual-e5-small
  (R@3 89.0, 12× faster than bge-m3). It's in the pipeline as
  `pipeline/embeddings.embed_for_retrieval`, using full transcripts (cutting
  them to 500 chars hurt).
- E3: SigLIP base, threshold 0.064. It's in the pipeline as
  `pipeline/video/creator_assets.py` (step 0 of AssetResolver), with a review UI.
- E1 v2 code: collect_reels.js, download_reels.py, distractor library
  (`--library all`), topic queries (`--queries topic`), make_topic_sheet.py.

## E1 v2 caption results (results/e1_summary_v2_caption.md)
102 docs (41/38/23), 92 caption queries, random R@3 9.4.

| method | R@3 | MRR | ms/query |
|---|---|---|---|
| bge-m3 | 78.6 | 71.1 | 381 |
| bm25+multi-e5-small | 76.5 | 71.1 | 38 |
| multi-e5-small | 75.6 | 65.4 | |
| bm25 | 73.7 | 68.8 | |
| minilm | 70.5 | 62.9 | |

Paired bootstrap: the hybrid is significantly better than multi-e5-small
(R@1 +8.7, MRR +5.4) and than minilm. multi-e5-small vs minilm is NOT
significant, so the v1 "e5 beats MiniLM" finding did not replicate. bge-m3
and the hybrid are tied.

Captions favour keywords, so **the retriever decision waits for the TOPIC
condition.** Candidate change: pipeline → hybrid BM25 + multi-e5-small (RRF).

## Next steps
1. Fill the `topic` column in `data/<Name> v2/topics.csv` for all 3 creators
   (0/102 filled on 2026-11-18). Rules are in make_topic_sheet.py.
2. Run:
   `python run_e1.py --creators "Rabika Tahir v2" "Hamza Bhatti v2" "Tech Wisdom v2" --queries topic --methods bge-m3 bm25+multi-e5-small bm25 multi-e5-small minilm --tag v2_topic`
3. Compare caption vs topic results with paired bootstrap. Write the v2
   section in REPORT.md. Decide whether the pipeline switches to the hybrid
   (if so, change `pipeline/embeddings` / the scripting agent's retrieval and
   re-run the 251+ tests).
4. Later: Whisper tiny → small in the pipeline (E1 used small); E2 (script
   style: none/random/MiniLM/E1-winner examples, authorship classifier +
   blind human test). E2 is designed but not built.

## Data
`data/` is git-ignored. This zip has captions.csv, topics.csv and
`transcripts_small_en.json` for every creator, but not the .mp4 files. The
mp4s are only needed if you re-transcribe; they're on the user's laptop
(1.7 GB). Hamza v2 has 12 carousel slides with no audio; the collector now
skips carousel_media.
