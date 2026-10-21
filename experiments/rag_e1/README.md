# E1 — Which search method best finds a creator's own past reels?

Standalone experiment for the text-RAG retrieval step. It does not import or
change any project code, and has its own virtual environment and requirements.

## The question

Before the Scripting Agent writes a script, RAG looks up the creator's most
relevant past transcripts. E1 measures how well different search methods do
that lookup, so the choice of embedding model is backed by numbers.

## How it works (known-item retrieval)

Reels have no titles, so the **cleaned caption** is the query:

```
reel 7 caption: "This serum changed my skin 😍 Link in bio #skincare"
        │  clean (drop emojis, hashtags, @mentions, "link in bio", ...)
        ▼
query:  "This serum changed my skin"   ──embed──►  compare with every transcript
                                                     of the SAME creator
correct answer: reel 7's own transcript  →  where did it rank? (1st? top 3?)
```

The answer key comes for free (caption i belongs to transcript i), so no
manual labelling is needed. Documents are transcripts only — captions are
never inside them, otherwise the match would be rigged.

## Methods compared

| Method | What it is |
|---|---|
| `bm25` | Keyword overlap, no neural network — classic baseline |
| `bert-raw`, `mbert-raw` | Plain BERT / multilingual BERT, mean-pooled. Not trained for similarity — the control that shows why sentence-embedding training matters |
| `minilm` | all-MiniLM-L6-v2 — **what the project uses now** |
| `mpnet` | all-mpnet-base-v2 — bigger English model |
| `bge-small`, `e5-small` | BERT-based models trained specifically for search |
| `multi-minilm`, `multi-e5-small`, `labse`, `bge-m3` | Multilingual models, for Urdu–English creators |
| `bm25+minilm`, `bm25+multi-e5-small` | Hybrid: keyword + embedding ranks merged with RRF (same as `qdrant_store.py`) |

Metrics: **R@1 / R@3 / R@5** (how often the correct transcript is in the top
1/3/5) and **MRR** (average of 1/rank). Each creator is evaluated separately,
then averaged; the random-guess baseline is shown for comparison. R@3 also
gets a 95% bootstrap confidence interval — with ~50 queries, differences of a
few points are within noise.

## Setup (once)

```powershell
cd experiments/rag_e1
python -m venv .venv
.venv\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

## Data layout

Videos and captions stay local (git-ignored). One folder per creator:

```
experiments/rag_e1/data/
  hashaam/
    captions.csv      ← see captions_template.csv
    reel_01.mp4
    reel_02.mp4
  tech_creator/
  beauty_creator/
```

`captions.csv` has two columns, `file` and `caption` (the caption exactly as
posted — cleaning happens in code). Save it as UTF-8 so Urdu and emojis
survive (Excel: *Save As → CSV UTF-8*).

Aim for **15–20 reels per creator** where the creator actually speaks.

## Run

```powershell
# 1. Transcribe — two conditions, each in its own file
python prepare_data.py --language en --out transcripts_small_en.json
python prepare_data.py --creators "Rabika Tahir" "Hamza Bhatti" --language ur --out transcripts_small_ur.json

# 2. Run the experiment on each condition
python run_e1.py --transcripts transcripts_small_en.json --tag en
python run_e1.py --transcripts transcripts_small_ur.json --tag ur
python run_e1.py --quick ...   # 6 methods instead of 13, faster

# Tests (no models or data needed)
python -m pytest tests
```

Results: `results/e1_summary.md` (tables for the report) and
`results/e1_results.json` (every query's rank and top match, for error analysis).

Models download from Hugging Face on first use (~2.5 GB for all methods;
`bge-m3` alone is ~2.2 GB — leave it out with `--methods` on a slow connection).

## Transcription language (found while preparing the data)

Whisper `small` with auto-detected language mislabels Pakistani Urdu–English
speech as Hindi and writes Devanagari script — sometimes garbage — which no
caption (English / Roman Urdu) can match. Checked on 2 reels each:

| Whisper setting | Output | Time per reel (CPU) |
|---|---|---|
| auto-detect | Hindi (Devanagari) script, partly garbage | 50–150 s |
| `--language ur` | Urdu (Arabic) script, readable | 40–90 s |
| `--language en` | Clean English — a *translation* of the speech | 15–20 s |

So E1 runs both conditions: **English transcripts** (Urdu speech translated
by Whisper) for all creators, and **Urdu-script transcripts** for the
Pakistani creators — testing whether search should translate first, or
whether multilingual models can search the Urdu directly. Note the English
version loses the creator's own code-mixed wording, which the Scripting
Agent needs for style; retrieval and style may need different transcripts.

## Choosing the winner

Decided **before** looking at results: pick the smallest model whose R@3 is
within ~2 points of the best, since everything runs locally.

## Limitations

- A caption is not the same as a topic from the Research Agent; it is a
  stand-in that gives a free answer key.
- E1 tests whether the right transcript is *found*, not whether it makes a
  better script — that is E2.
- Small per-creator libraries (15–20 reels) make the task easier than a
  large library would; report the random baseline alongside.
