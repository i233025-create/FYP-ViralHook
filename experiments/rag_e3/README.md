# E3 — Can the system pick the creator's right photo for each scene?

Standalone experiment for asset-grounded personalisation (visual RAG). It does
not import or change any project code.

## The question

The creator uploads photos (e.g. of FAST). The script has scenes like
*"students walking through the university main gate"*. Before a scene is
animated (image-to-video), the shot planner must pick the right photo — or
notice that none fits and fall back to stock / generation. E3 measures how
well different methods make that choice, so the model and the fallback
threshold are chosen from data before the feature is built.

## How it works

```
scene query: "Students walking through the university main gate"
      │ embed                              embed │
      ▼                                          ▼
 compare with every photo in assets/ + distractors/
      │
      ▼
 1. other_uni_gate.jpg   0.31  ✗ distractor
 2. fast_gate_1.jpg      0.30  ✓  ← first correct photo at rank 2
```

| Metric | Meaning |
|---|---|
| R@1 / R@3 / R@5, MRR | How often a correct photo is 1st / in the top 3 / top 5 (scenes that have one) |
| Distractor top-1 | How often a non-creator photo (e.g. another university's gate) wins — lower is better |
| No-match AUC | Whether the best photo's score separates "a photo fits" from "nothing fits" (1.0 perfect, 0.5 coin flip) |
| Threshold | The score below which the shot planner should fall back to stock / generation |
| Per-category R@3 | Gate, lab, library, logo... — where each method is strong or weak |

## Methods compared

| Method | Route | What it is |
|---|---|---|
| `clip-b32` | A | OpenAI CLIP ViT-B/32 — **what the project uses now** |
| `clip-l14` | A | Bigger CLIP |
| `siglip-base`, `siglip2-base` | A | Google SigLIP / SigLIP 2 — newer image–text models |
| `mclip` | A | Multilingual CLIP — for Urdu / Roman Urdu scene text |
| `caption` | B | BLIP describes each photo in words, then text search (bge-small) over the descriptions |
| `siglip-base+caption`, `clip-b32+caption` | C | Hybrid of A and B with Reciprocal Rank Fusion |

Route A compares photo and sentence directly. Route B turns photos into text
first — its captions (saved in `captions_blip.json`) can also feed the
Scripting Agent so scripts mention what is actually in the creator's photos.

## Setup

Uses the same virtual environment as E1:

```powershell
cd experiments/rag_e1
.venv\Scripts\activate
cd ../rag_e3
pip install -r requirements.txt
```

## Preparing the data

```
experiments/rag_e3/data/
  fast_admissions/
    assets/          ← YOUR FAST photos (jpg/png/webp; convert iPhone HEIC to JPG)
    distractors/     ← ~25 other photos: other universities' gates/libraries/labs
                       (hard) + random images like food, nature (easy)
    queries.csv      ← copy of queries_starter.csv, labelled (step 2)
```

**Step 1 — photos.** 20–30 FAST photos covering different places. Give them
readable names (`gate_1.jpg`, `lab_2.jpg`) — it makes labelling easier.

**Step 2 — label the scenes.** Copy `queries_starter.csv` to
`data/fast_admissions/queries.csv`. These scenes were written *without seeing
the photos* — the way a script would describe them — which keeps the test
fair. For each row:

- Put the photo(s) that fit the scene in `relevant_files`, separated by `;`
  (e.g. `gate_1.jpg;gate_2.jpg`).
- **If none of the photos fits, leave it empty.** Those become the "no match"
  scenes that measure the fallback threshold — keep at least ~10 of them.
- You may edit, delete or add scenes, but write new ones as a script would,
  not by describing a specific photo ("blue gate with a tree on the left"
  makes the test too easy).

Ideally the person labelling is not the one who will pick the winner.

## Run

```powershell
python run_e3.py --quick        # clip-b32, siglip-base, caption, hybrid
python run_e3.py                # all 8 methods
python -m pytest tests          # unit tests, no models or photos needed
```

Results: `results/e3_summary.md` (tables for the report) and
`results/e3_results.json` (top-3 photos for every scene, for error analysis).

First run downloads the models from Hugging Face (~4 GB for all methods;
`clip-l14` and BLIP-large are the largest). Everything runs on CPU; with ~70
photos the full run takes a few minutes, plus BLIP captioning (once, cached).

## Choosing the winner

Decided **before** looking at results: the smallest method within ~2 points
of the best R@3, with no-match AUC as the tie-breaker.

## Limitations

- Scenes are hand-written, not produced by the Scripting Agent; once the
  asset feature exists, re-run with real script scenes.
- The threshold is picked on the same scenes it is scored on, so it is
  optimistic — a starting value, to be checked on new scenes.
- One asset library shows the method; a second (e.g. a tech creator's
  product photos) is needed to claim it generalises.
