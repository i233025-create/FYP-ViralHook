# E1 — Caption → transcript retrieval

Run: 2026-10-21T15:45:38 · device: cpu · 3 creators, 41 queries

## Dataset

| Creator | Reels used / listed | Avg caption words | Avg transcript words | Caption script | Transcript script | Excluded |
|---|---|---|---|---|---|---|
| Hamza Bhatti | 17 / 17 | 10.7 | 162.2 | {'latin': 17} | {'latin': 17} | — |
| hashaam (skipped: < 5 usable reels) | 4 / 7 | 4.8 | 61.0 | {'latin': 4} | {'latin': 4} | {'caption < 4 words after cleaning': 3} |
| Rabika Tahir | 14 / 15 | 37.9 | 288.1 | {'latin': 14} | {'latin': 14} | {'transcript < 10 words': 1} |
| Tech Wisdom | 10 / 15 | 29.4 | 104.7 | {'latin': 10} | {'latin': 10} | {'no speech': 4, 'transcript < 10 words': 1} |

## Overall (macro average over creators, %)

95% CI from bootstrap over all queries. Ranked by MRR.

| Method | Family | Multilingual | Params (M) | R@1 | R@3 | R@5 | MRR | R@3 95% CI | Query ms |
|---|---|---|---|---|---|---|---|---|---|
| *random* | — | — | — | 7.7 | 23.0 | 38.4 | 24.2 | — | — |
| bge-m3 | sentence-embedding | yes | 567.8 | 70.1 | 90.4 | 92.7 | 80.8 | 80.5–97.6 | 246.0 |
| bm25+multi-e5-small | hybrid | yes | 117.7 | 65.0 | 86.1 | 94.7 | 77.6 | 78.0–97.6 | 16.8 |
| e5-small | sentence-embedding | no | 33.4 | 62.8 | 86.9 | 92.7 | 76.1 | 73.2–95.1 | 19.2 |
| bm25 | keyword | yes | — | 63.9 | 87.0 | 87.0 | 75.6 | 78.0–97.6 | 0.2 |
| multi-e5-small | sentence-embedding | yes | 117.7 | 58.1 | 89.0 | 95.7 | 74.0 | 80.5–97.6 | 20.1 |
| bge-small | sentence-embedding | no | 33.4 | 60.9 | 83.5 | 83.5 | 73.3 | 70.7–92.7 | 18.3 |
| bm25+minilm | hybrid | no | 22.7 | 52.8 | 82.7 | 90.4 | 69.7 | 70.7–92.7 | 9.4 |
| mpnet | sentence-embedding | no | 109.5 | 54.1 | 74.3 | 86.4 | 67.5 | 56.1–82.9 | 85.3 |
| labse | sentence-embedding | yes | 471.5 | 50.8 | 76.4 | 91.3 | 66.5 | 63.4–87.8 | 63.4 |
| minilm | sentence-embedding | no | 22.7 | 42.1 | 83.9 | 85.9 | 62.5 | 68.3–90.3 | 8.3 |
| multi-minilm | sentence-embedding | yes | 117.7 | 44.1 | 65.6 | 73.2 | 58.6 | 46.3–75.6 | 17.2 |
| bert-raw | raw-bert | no | 109.5 | 30.1 | 51.2 | 61.3 | 46.1 | 34.1–63.4 | 69.2 |
| mbert-raw | raw-bert | yes | 177.9 | 20.1 | 39.7 | 52.9 | 37.1 | 22.0–51.2 | 90.4 |

## R@3 per creator (%)

| Method | Hamza Bhatti | Rabika Tahir | Tech Wisdom |
|---|---|---|---|
| bge-m3 | 88.2 | 92.9 | 90.0 |
| bm25+multi-e5-small | 88.2 | 100.0 | 70.0 |
| e5-small | 70.6 | 100.0 | 90.0 |
| bm25 | 88.2 | 92.9 | 80.0 |
| multi-e5-small | 94.1 | 92.9 | 80.0 |
| bge-small | 70.6 | 100.0 | 80.0 |
| bm25+minilm | 82.4 | 85.7 | 80.0 |
| mpnet | 47.1 | 85.7 | 90.0 |
| labse | 70.6 | 78.6 | 80.0 |
| minilm | 58.8 | 92.9 | 100.0 |
| multi-minilm | 35.3 | 71.4 | 90.0 |
| bert-raw | 29.4 | 64.3 | 60.0 |
| mbert-raw | 23.5 | 35.7 | 60.0 |
