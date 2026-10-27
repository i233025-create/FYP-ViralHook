# Experiment E1 — Retrieval Model Selection for the Scripting Agent's Text RAG

**Project:** ViralHook — personalised short-form video generation (FYP)
**Date:** 21 October 2026
**Status:** Complete (English and Urdu-script transcript conditions)

---

## 1. Summary

Before the Scripting Agent writes a script, its retrieval step selects three of
the creator's past transcripts as style examples. This retriever used
`all-MiniLM-L6-v2`, a choice that had not been evaluated. E1 compares 13
retrieval methods on real Instagram reels from three creators (41 queries) to
choose the retriever on evidence.

**Decisions**

1. **Transcribe with Whisper forced to English (`language="en"`).** With
   automatic language detection, Whisper labels Pakistani Urdu–English speech
   as Hindi and outputs Devanagari script (partly unintelligible). Forcing
   English yields clean English translations and is 3–8× faster. Retrieval on
   Urdu-script transcripts is far worse (best top-3 accuracy 60% vs 94%).
2. **Replace MiniLM with `intfloat/multilingual-e5-small`.** It retrieves the
   correct transcript in the top 3 for 89.0% of queries (random: 23.0%) and
   ranks it first for 58.1%, versus 42.1% for MiniLM. The gain over MiniLM is
   statistically significant for top-1 accuracy and MRR. It is statistically
   indistinguishable from the most accurate model (bge-m3) while being ~5×
   smaller and ~12× faster, and it is the most robust method when transcripts
   are in Urdu script.

---

## 2. Motivation

The retrieval step determines which past transcripts the LLM imitates. If it
returns transcripts unrelated to the topic, the generated script is
conditioned on the wrong examples regardless of LLM quality. Retrieval can be
evaluated independently of script generation, so it is tested first (E1);
whether better retrieval produces scripts closer to the creator's style is a
separate question (planned E2).

## 3. Research questions

- **RQ1.** Which retrieval method best finds a creator's own past content for a
  given topic?
- **RQ2.** Does a sentence-embedding model outperform plain keyword matching
  and plain (non-fine-tuned) BERT?
- **RQ3.** For Pakistani creators who mix Urdu and English, should transcripts
  be translated to English before retrieval, or searched in Urdu script with a
  multilingual model?

---

## 4. Experimental setup

### 4.1 Task: known-item retrieval

Each reel provides a natural (query, answer) pair, so no manual relevance
labelling is required:

- **Query:** the reel's Instagram caption, cleaned (Section 4.3).
- **Documents:** the transcripts of all reels by the **same creator**. The
  system only ever searches one creator's library, so each creator is
  evaluated separately.
- **Correct answer:** the transcript of the reel the caption belongs to.

Captions are never part of the documents, so a match cannot be made by the
query text appearing inside its own answer.

### 4.2 Data

Public reels were downloaded locally (not redistributed; data is excluded from
version control).

| Creator | Niche | Language of speech | Reels collected | Reels used | Excluded |
|---|---|---|---|---|---|
| Hamza Bhatti | Food reviews | Urdu–English | 17 | 17 | — |
| Rabika Tahir | Beauty | Urdu–English | 15 | 14 | 1 (transcript < 10 words) |
| Tech Wisdom | Tech skits | English | 15 | 10 | 4 (no speech), 1 (transcript < 10 words) |
| Hashaam | Motivation | Urdu–English | 7 | 4 | 3 (caption < 4 words) → creator skipped |
| **Total evaluated** | | | | **41** | |

A creator needs at least 5 usable reels to be evaluated, so Hashaam was
excluded from the results. Rabika Tahir's captions were supplied in full;
Hamza Bhatti's and Hashaam's were recovered from download filenames (truncated
at ~100 characters, with lost line breaks restored).

### 4.3 Caption cleaning

URLs, @mentions, #hashtags, emojis and call-to-action boilerplate ("link in
bio", "follow for more", "products mentioned") were removed. Captions with fewer
than 4 words after cleaning were excluded because they carry no topic.

### 4.4 Transcription conditions

Whisper `small` (faster-whisper, int8, CPU, VAD filter, beam size 5).

| Condition | Whisper setting | Creators |
|---|---|---|
| **EN** | `language="en"` — Urdu–English speech is translated to English | All |
| **UR** | `language="ur"` — Urdu (Arabic) script | Hamza Bhatti, Rabika Tahir |

### 4.5 Methods compared (13)

| Method | Model | Family | Params (M) |
|---|---|---|---|
| bm25 | BM25 (Okapi) | Keyword | — |
| bert-raw | bert-base-uncased, mean pooling | Raw BERT | 110 |
| mbert-raw | bert-base-multilingual-cased, mean pooling | Raw BERT (multilingual) | 178 |
| minilm | sentence-transformers/all-MiniLM-L6-v2 (**current**) | Sentence embedding | 23 |
| mpnet | sentence-transformers/all-mpnet-base-v2 | Sentence embedding | 110 |
| bge-small | BAAI/bge-small-en-v1.5 | Sentence embedding (retrieval-trained) | 33 |
| e5-small | intfloat/e5-small-v2 | Sentence embedding (retrieval-trained) | 33 |
| multi-minilm | paraphrase-multilingual-MiniLM-L12-v2 | Multilingual sentence embedding | 118 |
| multi-e5-small | intfloat/multilingual-e5-small | Multilingual, retrieval-trained | 118 |
| labse | sentence-transformers/LaBSE | Multilingual sentence embedding | 472 |
| bge-m3 | BAAI/bge-m3 | Multilingual, retrieval-trained | 568 |
| bm25+minilm | Reciprocal Rank Fusion (k = 60) | Hybrid | 23 |
| bm25+multi-e5-small | Reciprocal Rank Fusion (k = 60) | Hybrid | 118 |

Each model used the query/passage prefixes it was trained with (e5: `query:` /
`passage:`; bge: its retrieval instruction). Dense methods use cosine
similarity of L2-normalised embeddings.

### 4.6 Metrics

- **R@1 / R@3 / R@5:** share of queries whose correct transcript is ranked in
  the top 1 / 3 / 5. **R@3 is the primary metric**, because the Scripting Agent
  receives the top 3 transcripts.
- **MRR:** mean reciprocal rank of the correct transcript.
- **Latency:** query encoding and scoring time per query (CPU).

Ties are ranked pessimistically (a method gains nothing from tied scores).
Metrics are macro-averaged over creators; the random-ranking baseline is
computed per creator from its library size.

### 4.7 Statistical analysis

95% confidence intervals by bootstrap over queries (2,000 resamples), and
**paired** bootstrap tests (10,000 resamples) on per-query differences between
key methods, since all methods are scored on the same queries.

### 4.8 Decision rule (fixed before results were seen)

> Choose the smallest model whose R@3 is within ~2 points of the best R@3,
> since every model must run locally on a CPU alongside the rest of the pipeline.

---

## 5. Results

### 5.1 Transcription language (RQ3, part 1)

On the reels inspected before the main run:

| Whisper setting | Output | Time per reel (CPU) |
|---|---|---|
| Auto-detect | Detected as Hindi; Devanagari script, partly unintelligible | 41–153 s |
| `language="ur"` | Readable Urdu script | 43–88 s |
| `language="en"` | Clean English translation, names preserved | 14–18 s |

Example (Hamza Bhatti, EN): *"Today we are trying KPG's Spicy Beef Tikka. This
is Haji Fazal Tikka Shop at Ashraf Road, Peshawar…"*

### 5.2 Main results — EN condition (3 creators, 41 queries)

Macro average over creators, %. Ranked by MRR.

| Method | Params (M) | R@1 | R@3 | R@5 | MRR | R@3 95% CI | ms / query |
|---|---|---|---|---|---|---|---|
| *random* | — | 7.7 | 23.0 | 38.4 | 24.2 | — | — |
| bge-m3 | 568 | **70.1** | **90.4** | 92.7 | **80.8** | 80.5–97.6 | 246.0 |
| bm25+multi-e5-small | 118 | 65.0 | 86.1 | 94.7 | 77.6 | 78.0–97.6 | 16.8 |
| e5-small | 33 | 62.8 | 86.9 | 92.7 | 76.1 | 73.2–95.1 | 19.2 |
| bm25 | — | 63.9 | 87.0 | 87.0 | 75.6 | 78.0–97.6 | 0.2 |
| **multi-e5-small** | 118 | 58.1 | 89.0 | **95.7** | 74.0 | 80.5–97.6 | 20.1 |
| bge-small | 33 | 60.9 | 83.5 | 83.5 | 73.3 | 70.7–92.7 | 18.3 |
| bm25+minilm | 23 | 52.8 | 82.7 | 90.4 | 69.7 | 70.7–92.7 | 9.4 |
| mpnet | 110 | 54.1 | 74.3 | 86.4 | 67.5 | 56.1–82.9 | 85.3 |
| labse | 472 | 50.8 | 76.4 | 91.3 | 66.5 | 63.4–87.8 | 63.4 |
| minilm (current) | 23 | 42.1 | 83.9 | 85.9 | 62.5 | 68.3–90.3 | 8.3 |
| multi-minilm | 118 | 44.1 | 65.6 | 73.2 | 58.6 | 46.3–75.6 | 17.2 |
| bert-raw | 110 | 30.1 | 51.2 | 61.3 | 46.1 | 34.1–63.4 | 69.2 |
| mbert-raw | 178 | 20.1 | 39.7 | 52.9 | 37.1 | 22.0–51.2 | 90.4 |

### 5.3 Results per creator — EN condition (R@3, %)

| Method | Hamza Bhatti (food, Urdu–English) | Rabika Tahir (beauty, Urdu–English) | Tech Wisdom (tech, English) |
|---|---|---|---|
| bge-m3 | 88.2 | 92.9 | 90.0 |
| multi-e5-small | **94.1** | 92.9 | 80.0 |
| bm25 | 88.2 | 92.9 | 80.0 |
| e5-small | 70.6 | 100.0 | 90.0 |
| minilm (current) | 58.8 | 92.9 | 100.0 |
| mpnet | 47.1 | 85.7 | 90.0 |
| bert-raw | 29.4 | 64.3 | 60.0 |

The Urdu–English food creator separates the models most: his captions name
dishes and places in Roman Urdu ("Nikka Siri Paye", "Chapli Kabab"). English
models trained on general text (MiniLM, mpnet) drop to 47–59%, while
multi-e5-small reaches 94.1%.

### 5.4 Paired comparisons — EN condition (41 queries)

Difference in percentage points (first method minus second), with 95% paired
bootstrap CI.

| Comparison | R@1 | R@3 | MRR | Conclusion |
|---|---|---|---|---|
| multi-e5-small − minilm | **+19.5** [+2.4, +36.6] | +9.8 [−4.9, +24.4] | **+14.6** [+3.4, +25.4] | Significantly better at rank 1 and MRR; top-3 gain not significant |
| bge-m3 − multi-e5-small | +9.8 [−7.3, +26.8] | 0.0 [−9.8, +9.8] | +5.2 [−5.5, +16.1] | No significant difference |
| multi-e5-small − bert-raw | **+31.7** [+12.2, +48.8] | **+41.5** [+24.4, +58.5] | **+30.8** [+18.2, +43.4] | Significantly better on all metrics |
| bm25+multi-e5-small − multi-e5-small | +7.3 [−7.3, +22.0] | −2.4 [−9.8, +4.9] | +4.0 [−5.2, +13.2] | No significant difference |
| multi-e5-small − bm25 | −4.9 [−22.0, +12.2] | +2.4 [−7.3, +12.2] | −1.2 [−12.8, +10.9] | No significant difference |

(Paired tests use queries pooled across creators, so values differ slightly
from the macro averages in 5.2.)

### 5.5 EN vs UR transcripts (RQ3) — same 2 creators, 31 queries

Macro average, %.

| Method | EN R@3 | UR R@3 | EN MRR | UR MRR |
|---|---|---|---|---|
| multi-e5-small | 93.5 | 54.4 | 77.1 | **52.9** |
| bge-m3 | 90.5 | **59.7** | 77.9 | 46.1 |
| labse | 74.6 | 55.0 | 62.5 | 45.6 |
| bm25+multi-e5-small | 94.1 | 58.0 | 80.5 | 44.3 |
| bm25 | 90.5 | 30.3 | 75.0 | 28.7 |
| e5-small | 85.3 | 29.6 | 73.6 | 28.0 |
| minilm (current) | 75.8 | 26.7 | 55.4 | 23.7 |
| *random* | ~22 | 19.5 | ~24 | 21.7 |

With Urdu-script transcripts, every method degrades sharply. English-only
models and BM25 fall to near random (captions are in Latin script, transcripts
in Arabic script, so they share almost no tokens). Only multilingual models
retain useful accuracy; multi-e5-small has the highest MRR.

### 5.6 Error analysis — multi-e5-small, EN

4 of 41 queries ranked the correct transcript below 3:

| Creator | Rank | Cleaned caption |
|---|---|---|
| Hamza Bhatti | 14 | "Roza lag raha hai" |
| Rabika Tahir | 7 | "All my eyeshadow palettes but all I want is palettes [...]" |
| Tech Wisdom | 4 | "AI will only replace you if it understands your code [...]" |
| Tech Wisdom | 5 | "Developers in 2022 vs 2026" |

Most failures are **teaser captions** that do not describe the video's content
("Roza lag raha hai", "Developers in 2022 vs 2026"). This is a limitation of
captions as queries rather than of the retriever; the same pattern made most of
Hashaam's captions unusable.

---

## 6. Discussion

**RQ1 — best method.** bge-m3 has the highest scores, but its advantage over
multi-e5-small, BM25 and the BM25 + multi-e5-small hybrid is not statistically
significant on 41 queries. By the pre-set rule (smallest model within ~2 points
of the best R@3: 89.0 vs 90.4), **multi-e5-small** is selected. It is ~5×
smaller and ~12× faster than bge-m3, which matters because every component runs
on a CPU.

**RQ2 — embeddings vs keywords vs raw BERT.**
- Raw BERT is significantly worse than sentence-embedding models (MRR 46.1 vs
  74.0). Pre-trained BERT is not trained for semantic similarity; the same
  architecture fine-tuned for sentence similarity and retrieval performs far
  better.
- BM25 is statistically as good as multi-e5-small on English transcripts. In
  this task captions and transcripts share exact names (restaurants, dishes,
  products), which favours keyword matching. multi-e5-small is still preferred
  because (a) BM25 collapses on Urdu-script transcripts (R@3 30.3 vs 54.4), and
  (b) in the full pipeline the query is a topic from the Research Agent, which
  will often not share exact words with past transcripts. The hybrid is a cheap
  optional addition, to be re-tested with topic queries.

**RQ3 — translate or search Urdu directly.** Translating to English with
Whisper is clearly better for retrieval (best R@3 ~94% vs ~60%). One caveat:
the English translation loses the creator's own code-mixed wording, which may
matter for *style imitation*. Retrieval should use the English transcript;
whether the Scripting Agent should be shown the original wording is a question
for E2.

**Effect of the change.** Replacing MiniLM with multi-e5-small raises top-1
accuracy from 42.1% to 58.1% (significant), and top-3 accuracy on the
Urdu–English food creator from 58.8% to 94.1%.

---

## 7. Limitations and threats to validity

1. **Small sample.** 41 queries from 3 creators; confidence intervals for the
   top methods overlap. Differences among the top group are not established.
2. **Captions as a proxy for topics.** The pipeline queries with Research Agent
   topics, not captions. Captions give a free answer key but are noisier
   (teasers, sponsor text) and favour keyword overlap.
3. **Small libraries.** 10–17 reels per creator; a real creator may have
   hundreds, which makes retrieval harder.
4. **Translated transcripts.** EN transcripts are Whisper translations, so
   wording is partly the translator's, not the creator's.
5. **Truncated captions.** Two creators' captions were recovered from
   filenames, cut off at ~100 characters.
6. **Single transcription model.** Only Whisper `small` was used; larger models
   may change the UR results.
7. **Retrieval only.** E1 shows the right transcripts are found, not that they
   produce better scripts (E2).

## 8. Next steps

1. Switch the Scripting Agent's retriever to multi-e5-small and the transcriber
   to `language="en"` (in the main pipeline, separately from this experiment).
2. Extend the dataset: more reels per creator (15–20+) and 1–2 more creators,
   including an English-only creator with spoken reels, and repeat E1 with
   Research-Agent-style topic queries.
3. **E2:** test whether retrieved examples improve style match compared with no
   examples and random examples.
4. **E3:** asset retrieval (scene description → creator's photo), code ready,
   awaiting labelled scene queries.

---

## 9. Reproducibility

Code: `experiments/rag_e1/` (isolated from the main project; own virtual
environment). Data and per-query results stay local and are git-ignored.

```powershell
python prepare_data.py --language en --out transcripts_small_en.json
python prepare_data.py --creators "Rabika Tahir" "Hamza Bhatti" --language ur --out transcripts_small_ur.json
python run_e1.py --transcripts transcripts_small_en.json --tag en
python run_e1.py --transcripts transcripts_small_ur.json --tag ur
```

Environment: Python 3.11.9, CPU only; torch 2.14.1+cpu, transformers 5.20.2,
sentence-transformers 6.1.0, faster-whisper 1.2.1 (Whisper `small`, int8).
Results are deterministic: re-running produced identical scores.
Full tables: `results/e1_summary_en.md`, `results/e1_summary_ur.md`.
