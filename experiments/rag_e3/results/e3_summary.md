# E3 — Scene → creator asset retrieval

Run: 2026-10-22T10:19:49 · device: cpu

## Dataset

| Library | Creator photos | Distractors | Scenes with a match | Scenes with no match | Categories |
|---|---|---|---|---|---|
| fast-admissions | 16 | 10 | 13 | 28 | {'gate': 2, 'campus': 6, 'lab': 3, 'library': 2, 'classroom': 3, 'cafeteria': 2, 'sports': 3, 'auditorium': 1, 'event': 6, 'logo': 1, 'admissions': 3, 'people': 3, 'transport': 1, 'graduation': 2, 'career': 2, 'hostel': 1} |

## Overall (%)

R@k / MRR over scenes that have a fitting photo. *Distractor top-1*: how often a non-creator photo won (lower is better). *No-match AUC*: how well the best creator-photo score separates 'a photo fits' from 'nothing fits' (100 = perfect, 50 = coin flip). ms/image and ms/query exclude model loading. Ranked by R@3.

| Method | Route | Params (M) | R@1 | R@3 | R@5 | MRR | R@3 95% CI | Distractor top-1 | No-match AUC | ms/image | ms/query |
|---|---|---|---|---|---|---|---|---|---|---|---|
| *random* | — | — | 6.1 | 17.0 | 27.6 | 18.9 | — | — | 50.0 | — | — |
| siglip-base | A: image–text embedding | 203.2 | 61.5 | 100.0 | 100.0 | 79.5 | 100.0–100.0 | 7.7 | 71.4 | 503.7 | 140.8 |
| clip-l14 | A: image–text embedding | 427.6 | 53.8 | 92.3 | 100.0 | 72.1 | 76.9–100.0 | 7.7 | 61.5 | 2140.9 | 33.0 |
| siglip2-base | A: image–text embedding | 375.2 | 61.5 | 92.3 | 100.0 | 76.3 | 76.9–100.0 | 7.7 | 73.4 | 496.8 | 141.2 |
| siglip-base+caption | C: hybrid (RRF) | 706.6 | 61.5 | 92.3 | 100.0 | 76.3 | 76.9–100.0 | 0.0 | — | 396.9 | 124.5 |
| clip-b32 | A: image–text embedding | 151.3 | 53.8 | 84.6 | 92.3 | 70.8 | 61.5–100.0 | 15.4 | 59.3 | 111.5 | 13.0 |
| mclip | A: image–text embedding | 286.4 | 46.2 | 76.9 | 100.0 | 66.5 | 53.8–100.0 | 15.4 | 53.8 | 119.9 | 14.7 |
| clip-b32+caption | C: hybrid (RRF) | 654.7 | 46.2 | 76.9 | 92.3 | 65.1 | 53.8–100.0 | 7.7 | — | 116.3 | 24.0 |
| caption | B: caption → text search | 503.4 | 23.1 | 61.5 | 69.2 | 43.6 | 38.5–84.6 | 38.5 | 76.1 | 11.0 | 11.4 |

## Fallback threshold (best similarity score below this → use stock / generation)

Chosen on the same scenes it is scored on, so treat it as a starting value.

| Method | Library | Threshold | Matching scenes kept | No-match scenes sent to fallback |
|---|---|---|---|---|
| siglip-base | fast-admissions | 0.064 | 61.5 | 82.1 |
| clip-l14 | fast-admissions | 0.205 | 84.6 | 42.9 |
| siglip2-base | fast-admissions | 0.108 | 69.2 | 71.4 |
| clip-b32 | fast-admissions | 0.273 | 38.5 | 89.3 |
| mclip | fast-admissions | 0.283 | 38.5 | 96.4 |
| caption | fast-admissions | 0.672 | 53.8 | 96.4 |

## R@3 per scene category (%)

| Method | auditorium | cafeteria | campus | classroom | event | lab | people |
|---|---|---|---|---|---|---|---|
| siglip-base | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| clip-l14 | 0.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| siglip2-base | 100.0 | 100.0 | 50.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| siglip-base+caption | 100.0 | 100.0 | 100.0 | 50.0 | 100.0 | 100.0 | 100.0 |
| clip-b32 | 0.0 | 100.0 | 100.0 | 100.0 | 66.7 | 100.0 | 100.0 |
| mclip | 0.0 | 100.0 | 100.0 | 50.0 | 66.7 | 100.0 | 100.0 |
| clip-b32+caption | 0.0 | 50.0 | 100.0 | 50.0 | 100.0 | 100.0 | 100.0 |
| caption | 0.0 | 0.0 | 100.0 | 0.0 | 100.0 | 100.0 | 100.0 |
