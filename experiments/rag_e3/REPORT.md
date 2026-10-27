# Experiment E3 — Visual Retrieval of Creator Assets for Shot Planning

**Project:** ViralHook — personalised short-form video generation (FYP)
**Date:** 22 October 2026
**Status:** Complete (one asset library: FAST admissions)

---

## 1. Summary

Personalisation in ViralHook includes building videos around assets the
creator supplies (e.g. photos of their university for an "Admissions Open"
reel). For every scene of the script, the shot planner must pick the creator
photo that fits the scene, or recognise that none fits and fall back to
generating a visual. E3 compares 8 retrieval methods for this step on a
library of 16 FAST photos plus 10 distractor photos of other universities,
using 41 scene descriptions labelled by the team.

**Decisions**

1. **Use SigLIP (`google/siglip-base-patch16-224`) for asset retrieval,
   replacing CLIP ViT-B/32.** SigLIP placed a correct FAST photo in the top 3
   for all 13 scenes that had one (CLIP B/32: 11 of 13), ranked it first for
   8 of 13, and picked another university's photo first only once. It is the
   only method that satisfies the pre-set decision rule.
2. **Describe-then-search (BLIP captions) is rejected.** It was significantly
   worse than SigLIP (top-3 accuracy 61.5% vs 100%) and ~13× slower to index
   each photo.
3. **A similarity threshold alone is not reliable enough to decide fallback.**
   With SigLIP, the best threshold (0.064) sends 82% of no-match scenes to
   generation but also drops 38% of scenes that do have a fitting photo. The
   threshold is used as a default, and the creator confirms or swaps the
   chosen photo in a review step.

---

## 2. Motivation

The supervisor's feedback defined personalisation to include creator-supplied
assets, in addition to voice, script style and visual style. In the planned
flow, assets are uploaded with the video idea (per-video assets) or once at
onboarding (brand kit), embedded at upload time, and matched to script scenes
by the shot planner. Matched photos are animated with an image-to-video model.

If retrieval picks the wrong photo, the scene is wrong regardless of the
quality of the video model, so this step is evaluated on its own, before the
feature is built, to choose the model and the fallback threshold from data.

## 3. Research questions

- **RQ1.** Which method best matches a script scene to the creator's correct
  photo?
- **RQ2.** Does the method distinguish the creator's own location from similar
  places (other universities)?
- **RQ3.** Can the similarity score tell when *no* creator photo fits, so the
  system falls back to generation?
- **RQ4.** Is it better to compare images and text directly, or to caption
  images first and search the captions as text?

---

## 4. Experimental setup

### 4.1 Asset library

| Folder | Count | Content |
|---|---|---|
| `assets/` (creator photos) | 16 | FAST Islamabad: campus exterior and aerial views (3), sports court (1), computer labs / meeting room (2), lecture halls / auditorium (3), cafeteria (2), corridors (2), events — night event and speaker (2), faculty office (1) |
| `distractors/` | 10 | Exteriors of other Pakistani universities (e.g. Air University, Bahria University), some with name signs |

All 26 images are searched together; only creator photos can be correct.

### 4.2 Scene queries and labels

- 41 scene descriptions for an admissions reel were written **before the
  photos were seen**, in the generic wording a script would use (e.g. "A busy
  cafeteria where students eat and chat").
- A team member labelled each scene with the FAST photo(s) that fit it, or
  left it empty if none fits. A consistency review flagged 7 rows (e.g.
  corridor and cafe scenes left empty although a photo fits; a gate scene
  labelled with an indoor photo); the labeller revised all 7 before the run.
- Result: **13 scenes with at least one fitting photo** (campus 2, lab 2,
  classroom 2, cafeteria 2, auditorium 1, event 3, people 1) and **28 scenes
  with none** (e.g. library, main gate, graduation, hostel, sports field).

### 4.3 Methods compared (8)

| Method | Route | Model(s) | Params (M) |
|---|---|---|---|
| clip-b32 | A: image–text embedding | OpenAI CLIP ViT-B/32 — **currently used in the project** | 151 |
| clip-l14 | A | OpenAI CLIP ViT-L/14 | 428 |
| siglip-base | A | Google SigLIP base, patch 16, 224 px | 203 |
| siglip2-base | A | Google SigLIP 2 base, patch 16, 224 px | 375 |
| mclip | A | CLIP ViT-B/32 image encoder + multilingual text encoder | 286 |
| caption | B: caption → text search | BLIP-large captions each photo; bge-small-en-v1.5 matches scenes to captions | 503 |
| siglip-base+caption | C: hybrid | Reciprocal Rank Fusion (k = 60) of siglip-base and caption | 707 |
| clip-b32+caption | C: hybrid | Reciprocal Rank Fusion (k = 60) of clip-b32 and caption | 655 |

Route A models encode images and text into a shared embedding space trained
contrastively on image–caption pairs; scenes are matched to photos by cosine
similarity. CLIP is trained with a softmax loss over the batch, SigLIP with a
pairwise sigmoid loss. Route B converts each photo to a caption and reduces
the task to text retrieval.

### 4.4 Metrics

Scenes **with** a fitting photo (13):
- **R@1 / R@3 / R@5:** share of scenes whose first correct photo is ranked in
  the top 1 / 3 / 5. Ties ranked pessimistically.
- **MRR:** mean reciprocal rank of the first correct photo.
- **Distractor top-1:** share of scenes where another university's photo was
  ranked first (lower is better).

All 41 scenes — **fallback decision**:
- **No-match AUC:** how well the best *creator-photo* similarity separates
  scenes with a fitting photo from scenes without one (100 = perfect, 50 =
  chance). Distractors are excluded from this score, because in the product
  the library holds only the creator's photos. (An initial run included them,
  so a genuinely matching distractor — another university's name sign for
  "The university entrance with its name sign" — counted as "a photo fits";
  the metric was corrected before the results below.)
- **Threshold:** the similarity cut-off that maximises balanced accuracy
  (share of matching scenes kept + share of no-match scenes sent to fallback,
  divided by 2).

Speed (CPU, model loading excluded): indexing time per photo (done once, at
upload) and time per scene query.

### 4.5 Statistical analysis

95% bootstrap confidence intervals over scenes, and paired bootstrap tests
(10,000 resamples) of per-scene differences between key methods.

### 4.6 Decision rule (fixed before results were seen)

> Choose the smallest method whose R@3 is within ~2 points of the best R@3,
> with no-match AUC as the tie-breaker.

---

## 5. Results

### 5.1 Main results

%, ranked by R@3.

| Method | Params (M) | R@1 | R@3 | R@5 | MRR | R@3 95% CI | Distractor top-1 | No-match AUC | ms / photo (index) | ms / scene |
|---|---|---|---|---|---|---|---|---|---|---|
| *random* | — | 6.1 | 17.0 | 27.6 | 18.9 | — | — | 50.0 | — | — |
| **siglip-base** | 203 | **61.5** | **100.0** | 100.0 | **79.5** | 100.0–100.0 | 7.7 | 71.4 | 504 | 141 |
| siglip2-base | 375 | 61.5 | 92.3 | 100.0 | 76.3 | 76.9–100.0 | 7.7 | 73.4 | 497 | 141 |
| clip-l14 | 428 | 53.8 | 92.3 | 100.0 | 72.1 | 76.9–100.0 | 7.7 | 61.5 | 2,141 | 33 |
| siglip-base+caption | 707 | 61.5 | 92.3 | 100.0 | 76.3 | 76.9–100.0 | **0.0** | — | ≈ 6,900* | 125 |
| clip-b32 (current) | 151 | 53.8 | 84.6 | 92.3 | 70.8 | 61.5–100.0 | 15.4 | 59.3 | 112 | 13 |
| mclip | 286 | 46.2 | 76.9 | 100.0 | 66.5 | 53.8–100.0 | 15.4 | 53.8 | 120 | 15 |
| clip-b32+caption | 655 | 46.2 | 76.9 | 92.3 | 65.1 | 53.8–100.0 | 7.7 | — | ≈ 6,500* | 24 |
| caption | 503 | 23.1 | 61.5 | 69.2 | 43.6 | 38.5–84.6 | 38.5 | 76.1 | ≈ 6,400* | 11 |

\* BLIP captioning measured on the first (uncached) run at ~6.4 s per photo;
captions are cached afterwards. Hybrid AUC is not reported because RRF scores
are rank-based and cannot be thresholded.

### 5.2 Rank of the first correct photo, per scene

| Scene | siglip-base | siglip2-base | clip-l14 | clip-b32 | mclip | caption |
|---|---|---|---|---|---|---|
| A wide shot of the campus buildings on a sunny day | 3 | 4 | 2 | 1 | 1 | 3 |
| An aerial view of the whole university campus | 1 | 1 | 1 | 1 | 1 | 2 |
| A modern computer lab with rows of computers | 1 | 1 | 1 | 2 | 1 | 1 |
| Students coding together on laptops | 2 | 2 | 1 | 1 | 2 | 2 |
| A lecture hall full of students listening to a teacher | 2 | 2 | 3 | 3 | 2 | 8 |
| A teacher explaining something on a whiteboard | 1 | 1 | 1 | 1 | 4 | 11 |
| A busy cafeteria where students eat and chat | 2 | 3 | 2 | 2 | 2 | 6 |
| Friends laughing together over chai and snacks | 1 | 1 | 2 | 1 | 1 | 12 |
| A large auditorium with a stage | 1 | 1 | 5 | **6** | 5 | 5 |
| A speaker giving a talk on stage to a crowd | 1 | 1 | 3 | 2 | 2 | 1 |
| A society or club event with decorations | 1 | 1 | 1 | 1 | 1 | 3 |
| Students celebrating a festival on campus | 2 | 3 | 1 | **5** | 5 | 3 |
| Students walking between classes in a corridor | 1 | 1 | 1 | 1 | 1 | 1 |

SigLIP never ranks a correct photo below 3. CLIP B/32 fails on the auditorium
(rank 6, behind a distractor building) and the festival scene (rank 5).

### 5.3 Paired comparisons

Difference in percentage points over the 13 scenes, with 95% paired bootstrap CI.

| Comparison | R@1 | R@3 | MRR | Conclusion |
|---|---|---|---|---|
| siglip-base − clip-b32 | +7.7 [−23.1, +38.5] | +15.4 [0.0, +38.5] | +8.7 [−11.8, +29.2] | Better on every metric, not statistically significant on 13 scenes |
| siglip-base − siglip2-base | 0.0 [0.0, 0.0] | +7.7 [0.0, +23.1] | +3.2 [0.0, +7.1] | Equal or slightly better; not significant |
| siglip-base − caption | **+38.5** [+15.4, +61.5] | **+38.5** [+15.4, +61.5] | **+35.9** [+17.3, +55.8] | Significantly better on all metrics |

### 5.4 Distinguishing FAST from other universities (RQ2)

| Method | Scenes where a distractor ranked first | Cases |
|---|---|---|
| siglip-base | 1 of 13 | "Wide shot of the campus buildings" → another university's building (correct at rank 3) |
| clip-b32 | 2 of 13 | Auditorium → another university's building; festival → another university's lawn |
| caption | 5 of 13 | Mostly building and people scenes |

Every distractor is a university exterior, so this tests campus-level scenes
only; indoor distractors (other universities' labs, classrooms) were not
included.

### 5.5 Fallback decision (RQ3)

| Method | No-match AUC | Threshold | Matching scenes kept | No-match scenes sent to fallback |
|---|---|---|---|---|
| siglip-base | 71.4 | 0.064 | 61.5% | 82.1% |
| siglip2-base | 73.4 | 0.108 | 69.2% | 71.4% |
| clip-l14 | 61.5 | 0.205 | 84.6% | 42.9% |
| clip-b32 | 59.3 | 0.273 | 38.5% | 89.3% |
| mclip | 53.8 | 0.283 | 38.5% | 96.4% |
| caption | 76.1 | 0.672 | 53.8% | 96.4% |

No method separates the two groups well. The no-match scenes with the highest
SigLIP scores show why: the library contains *adjacent* photos.

| No-match scene | Best creator photo | SigLIP score |
|---|---|---|
| A convocation ceremony with students in gowns | 12.jpeg (orientation ceremony on stage) | 0.095 |
| A student working at an internship in a tech company office | 9.jpeg (meeting room with projector) | 0.073 |
| A student receiving an award on stage | 12.jpeg | 0.071 |
| Students presenting their project at a stall | 16.jpeg (students in an atrium) | 0.070 |
| Students walking through the university main gate | 16.jpeg | 0.070 |

These score as high as some correct matches (e.g. "A modern computer lab",
0.064). Whether such a photo is acceptable is partly a judgement call, which
a fixed threshold cannot make.

### 5.6 Caption route (RQ4)

BLIP's captions are generic and lose the details that distinguish photos:

| Photo | BLIP caption |
|---|---|
| 3.jpeg (FAST main building) | "there is a large building with a green dome on top of it" |
| 11.jpeg (auditorium) | "there are many people sitting in chairs in a lecture hall" |
| 12.jpeg (orientation ceremony) | "there are two women standing at a podium in front of a crowd" |
| 14.jpeg (cafe inauguration) | "there are people standing in line at the counter of a cafe" |
| distractors/1.jfif | "an image of a building with a sign that says air university karachi campus" |

BLIP read the name signs on two distractor buildings but none of the FAST
event banners. The caption route has the best no-match AUC (76.1), but only
because its retrieval is poor overall; it is not usable for matching.

---

## 6. Discussion

**RQ1 — best method.** SigLIP base is the only method with a correct photo in
the top 3 for every scene, and by the pre-set rule it is selected (best R@3,
and no method is within 2 points). Its advantage over CLIP B/32 is consistent
across metrics but not statistically significant on 13 scenes. SigLIP 2 is
equivalent in practice and has a slightly higher no-match AUC, but it is
nearly twice the size. Indexing costs ~0.5 s per photo on CPU, paid once per
upload; a scene query takes ~0.14 s.

**RQ2 — own location vs similar places.** SigLIP confused FAST with another
university once in 13 scenes, CLIP B/32 twice. With exterior-only distractors
this result covers campus-level scenes, not indoor ones.

**RQ3 — fallback.** Similarity alone separates "a photo fits" from "nothing
fits" only moderately (AUC 71 for SigLIP). The errors are mostly photos that
are related to the scene but not quite right (a ceremony photo for a
convocation). The design therefore uses the threshold as a **default**, and
the creator reviews and can swap the chosen photo for each scene before the
video is rendered.

**RQ4 — direct vs caption-first.** Direct image–text embedding is clearly
better. Captioning with BLIP discards distinguishing detail and is ~13×
slower per photo. A stronger vision-language captioner could change this and
would also give the Scripting Agent text descriptions of the assets; that is
left for future work.

**Effect of the change.** Replacing CLIP B/32 with SigLIP raises top-3
accuracy from 84.6% to 100% (11 → 13 of 13 scenes) and no-match AUC from 59.3
to 71.4, at ~4.5× the per-photo indexing cost.

---

## 7. Limitations and threats to validity

1. **Few matching scenes.** Only 13 scenes have a fitting photo, so
   confidence intervals are wide and most differences between the top
   methods are not significant.
2. **Small library.** 16 creator photos from one institution; a real creator
   may upload more and more varied assets.
3. **Exterior-only distractors.** No indoor distractors, so the test does not
   show whether FAST's lab can be told apart from another university's lab.
4. **Threshold fitted and evaluated on the same scenes.** The reported
   threshold is optimistic; it is a starting value to validate on new scenes.
5. **Hand-written scenes.** Scenes were written by hand, not produced by the
   Scripting Agent; real script scenes may be longer or more specific.
6. **Text in images.** Several FAST photos carry event banners with text
   (e.g. "CAFE INAUGURATION CEREMONY"); models that read text may be helped on
   some scenes.
7. **Single labeller.** Labels come from one team member, revised once.

## 8. Next steps

1. Use SigLIP for asset retrieval in the shot planner, with the threshold as
   the default and a per-scene review/swap step in the production screen.
2. Extend the library: indoor distractors (other universities' labs,
   classrooms, cafeterias), more FAST photos, and a second asset library
   (e.g. a creator's product photos) to test generalisation.
3. Re-run with scenes produced by the Scripting Agent once the asset feature
   is integrated, and validate the threshold on new scenes.
4. Evaluate whether SigLIP should also replace CLIP in Module 2 (video
   embeddings, talking-head detection) and in the video evaluator; those uses
   were not tested here.

---

## 9. Reproducibility

Code: `experiments/rag_e3/` (isolated from the main project; shares the E1
virtual environment). Photos and labels stay local and are git-ignored.

```powershell
cd experiments/rag_e3
python run_e3.py              # all 8 methods
python -m pytest tests        # unit tests
```

Data layout: `data/fast-admissions/assets/`, `data/fast-admissions/distractors/`,
`data/fast-admissions/queries.csv`.

Environment: Python 3.11.9, CPU only; torch 2.14.1+cpu, transformers 5.20.2,
sentence-transformers 6.1.0. Run of 22 October 2026, 10:19.
Full tables: `results/e3_summary.md`; per-scene top-3 results and BLIP captions:
`results/e3_results.json` (local only).
