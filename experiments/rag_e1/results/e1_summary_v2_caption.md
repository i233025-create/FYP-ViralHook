# E1 — Caption → transcript retrieval

Run: 2026-11-08T18:51:32 · device: cpu · 3 creators, 92 queries · queries: caption · library: all

## Dataset

| Creator | Reels listed | Library (docs) | Queries | Avg query words | Avg transcript words | Query script | Transcript script | Not in library | No usable query |
|---|---|---|---|---|---|---|---|---|---|
| Hamza Bhatti v2 | 50 | 38 | 30 | 19.9 | 140.6 | {'latin': 29, 'arabic': 1} | {'latin': 38} | {'no speech': 12} | {'caption < 4 words after cleaning': 8} |
| Rabika Tahir v2 | 50 | 41 | 39 | 30.9 | 223.7 | {'latin': 39} | {'latin': 41} | {'transcript < 10 words': 6, 'no speech': 3} | {'caption < 4 words after cleaning': 2} |
| Tech Wisdom v2 | 50 | 23 | 23 | 42.8 | 100.6 | {'latin': 23} | {'latin': 23} | {'no speech': 19, 'transcript < 10 words': 8} | — |

## Overall (macro average over creators, %)

95% CI from bootstrap over all queries. Ranked by MRR.

| Method | Family | Multilingual | Params (M) | R@1 | R@3 | R@5 | MRR | R@3 95% CI | Query ms |
|---|---|---|---|---|---|---|---|---|---|
| *random* | — | — | — | 3.1 | 9.4 | 15.7 | 12.6 | — | — |
| bge-m3 | sentence-embedding | yes | 567.8 | 61.6 | 78.6 | 84.0 | 71.1 | 67.4–84.8 | 381.1 |
| bm25+multi-e5-small | hybrid | yes | 117.7 | 61.7 | 76.5 | 81.3 | 71.1 | 65.2–82.6 | 37.6 |
| bm25 | keyword | yes | — | 60.5 | 73.7 | 78.2 | 68.8 | 60.9–80.4 | 0.6 |
| multi-e5-small | sentence-embedding | yes | 117.7 | 52.6 | 75.6 | 81.0 | 65.4 | 64.1–81.5 | 38.3 |
| minilm | sentence-embedding | no | 22.7 | 50.5 | 70.5 | 81.0 | 62.9 | 57.6–77.2 | 13.3 |

## R@3 per creator (%)

| Method | Hamza Bhatti v2 | Rabika Tahir v2 | Tech Wisdom v2 |
|---|---|---|---|
| bge-m3 | 90.0 | 59.0 | 87.0 |
| bm25+multi-e5-small | 76.7 | 61.5 | 91.3 |
| bm25 | 73.3 | 56.4 | 91.3 |
| multi-e5-small | 76.7 | 59.0 | 91.3 |
| minilm | 73.3 | 51.3 | 87.0 |
