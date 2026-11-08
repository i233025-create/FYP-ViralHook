# E1 — Caption → transcript retrieval

Run: 2026-10-21T15:41:54 · device: cpu · 2 creators, 31 queries

## Dataset

| Creator | Reels used / listed | Avg caption words | Avg transcript words | Caption script | Transcript script | Excluded |
|---|---|---|---|---|---|---|
| Hamza Bhatti | 17 / 17 | 10.7 | 179.9 | {'latin': 17} | {'arabic': 17} | — |
| hashaam (skipped: < 5 usable reels) | 0 / 7 | 0 | 0 | {} | {} | {'not transcribed': 7} |
| Rabika Tahir | 14 / 15 | 37.9 | 216.0 | {'latin': 14} | {'arabic': 10, 'latin': 4} | {'transcript < 10 words': 1} |
| Tech Wisdom (skipped: < 5 usable reels) | 0 / 15 | 0 | 0 | {} | {} | {'not transcribed': 15} |

## Overall (macro average over creators, %)

95% CI from bootstrap over all queries. Ranked by MRR.

| Method | Family | Multilingual | Params (M) | R@1 | R@3 | R@5 | MRR | R@3 95% CI | Query ms |
|---|---|---|---|---|---|---|---|---|---|
| *random* | — | — | — | 6.5 | 19.5 | 32.6 | 21.7 | — | — |
| multi-e5-small | sentence-embedding | yes | 117.7 | 37.8 | 54.4 | 71.0 | 52.9 | 38.7–71.0 | 17.1 |
| bge-m3 | sentence-embedding | yes | 567.8 | 25.4 | 59.7 | 69.7 | 46.1 | 41.9–77.4 | 217.9 |
| labse | sentence-embedding | yes | 471.5 | 26.1 | 55.0 | 67.4 | 45.6 | 38.7–71.0 | 56.0 |
| bm25+multi-e5-small | hybrid | yes | 117.7 | 23.7 | 58.0 | 66.8 | 44.3 | 38.7–74.2 | 15.7 |
| bm25+minilm | hybrid | no | 22.7 | 19.5 | 29.0 | 42.6 | 32.0 | 12.9–45.2 | 8.4 |
| bm25 | keyword | yes | — | 16.6 | 30.3 | 33.8 | 28.7 | 12.9–45.2 | 0.2 |
| e5-small | sentence-embedding | no | 33.4 | 13.7 | 29.6 | 36.8 | 28.0 | 12.9–45.2 | 24.5 |
| mpnet | sentence-embedding | no | 109.5 | 13.7 | 23.1 | 36.1 | 27.8 | 9.7–35.5 | 118.2 |
| multi-minilm | sentence-embedding | yes | 117.7 | 10.7 | 23.1 | 47.5 | 27.2 | 9.7–38.7 | 20.1 |
| minilm | sentence-embedding | no | 22.7 | 6.5 | 26.7 | 29.6 | 23.7 | 9.7–41.9 | 8.6 |
| bert-raw | raw-bert | no | 109.5 | 6.5 | 22.5 | 32.6 | 23.4 | 9.7–38.7 | 62.6 |
| mbert-raw | raw-bert | yes | 177.9 | 6.5 | 19.5 | 35.5 | 22.6 | 6.5–32.3 | 92.6 |
| bge-small | sentence-embedding | no | 33.4 | 7.1 | 17.2 | 33.2 | 22.5 | 3.2–29.0 | 29.9 |

## R@3 per creator (%)

| Method | Hamza Bhatti | Rabika Tahir |
|---|---|---|
| multi-e5-small | 58.8 | 50.0 |
| bge-m3 | 76.5 | 42.9 |
| labse | 52.9 | 57.1 |
| bm25+multi-e5-small | 58.8 | 57.1 |
| bm25+minilm | 29.4 | 28.6 |
| bm25 | 17.6 | 42.9 |
| e5-small | 23.5 | 35.7 |
| mpnet | 17.6 | 28.6 |
| multi-minilm | 17.6 | 28.6 |
| minilm | 17.6 | 35.7 |
| bert-raw | 23.5 | 21.4 |
| mbert-raw | 17.6 | 21.4 |
| bge-small | 5.9 | 28.6 |
