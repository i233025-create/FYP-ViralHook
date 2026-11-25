# Research Agent: V1 (YouTube) vs V2 (Instagram), full report

**Date:** 2026-11-18 · **Branch:** `feat/research-agent-v2` · **Experiment:** `experiments/trend_e1/`

This document covers what was built, how both versions work, how the
Instagram access was set up, every result from the live runs, what works,
what doesn't, and what to do next.

---

## 1. Summary

| Question | Answer |
|---|---|
| Were both versions built? | Yes. One shared Research Agent core, with two data sources switched by `TREND_SOURCE=youtube` or `instagram`. |
| Were both tested live? | Yes, on 2 niches (motivation, fitness_beginners), with the same search queries for both versions. |
| Which one is better? | **V1 YouTube, clearly.** V1 found 3 `trend`s + 1 `emerging` (fitness) and sensible `evergreen` topics. V2 found **no trend in either niche**. |
| Why did V2 fail? | (1) Hashtag Search needs Meta App Review, so V2 ran on creator lists only. (2) Big creators' captions don't say the topic. (3) 15 fixed creators rarely post on the same topic. |
| Is V1 perfect? | No. 1 of its 3 fitness trends is noise (tiny channels), and 2 are mixed clusters. Fixes are listed in section 10. |
| Recommendation | Use V1 as the source. Keep V2 in the code for the creator's *own* Instagram data (W2 "past performance"). |

---

## 2. The question

The Research Agent finds what is trending in a creator's niche. Until now it
only used YouTube. The question was whether Instagram, the platform most
short-form creators actually post on, gives better trends, using only
official and free APIs. X/Twitter was dropped because it is paid.

---

## 3. The trend definition (shared by both versions)

Defined in `docs/trend_sources_comparison.pdf`, section 3, and implemented in
`pipeline/agents/research_agent.py`.

A cluster of posts on one topic gets **4 checks**:

| Check | Rule | Default (overridable in `.env`) |
|---|---|---|
| **Overperforms** | median outlier ≥ 1.5 (posts get more than their creator normally gets) | `TREND_OVERPERFORM_OUTLIER=1.5` |
| **Growing** | relative growth ≥ 1.3 (uploads in the last 3 days vs the 11 days before, compared with the whole niche) | `TREND_GROWTH_RATIO_MIN=1.3`, `TREND_RECENT_WINDOW_DAYS=3` |
| **Spreading** | ≥ 3 different creators | `TREND_MIN_TREND_CHANNELS=3` |
| **Recent** | median post age ≤ 14 days | `SEARCH_PUBLISHED_DAYS=14` |

Then a **trend_type**:

| trend_type | Meaning | Shown to user? |
|---|---|---|
| `trend` | all 4 checks pass | ✅ high confidence |
| `emerging` | overperforms + growing, but only 2 creators | ✅ low confidence |
| `evergreen` | spreading, but not growing (always popular) | ✅ low confidence |
| `topic` | anything else with ≥ 2 creators | ✅ low confidence |
| `one_off_viral` | overperforms, but only 1 creator | ❌ hidden |
| `single_creator` | 1 creator, not overperforming | ❌ hidden |

**Ranking:** by type first (trend → emerging → evergreen → topic), then by:
`trend_score = 0.35 × strength + 0.20 × growth + 0.15 × spread + 0.30 × creator_fit`

Clusters with `creator_fit < 0.45` (cosine similarity to the creator's recurring
topics) are dropped before any of this. A viral topic outside the
creator's niche is not a trend for them.

### Relative growth (how "growing" is measured)

```
cluster odds = (recent + p·m) / (earlier + (1−p)·m)      m = 2 pseudo-posts
niche odds   = p / (1 − p)                               p = recent share of ALL posts
relative_growth = cluster odds ÷ niche odds
```

This equals (cluster's upload-rate ratio) ÷ (niche's upload-rate ratio). It
was needed because of the two bugs described in section 9.

---

## 4. Architecture

```
                       ┌─ V1: YouTube Data API (research_agent.py)
 queries (local LLM) ──┤
                       └─ V2: Instagram Graph API (instagram_source.py)
                                      │
                    same post shape ▼ (text, likes, views, author, followers, time)
      score → embed (MiniLM) → collapse duplicates → cluster → trend definition → LLM label
```

Everything after data collection is the **same code**, so the comparison is fair.

| File | What it does |
|---|---|
| `pipeline/agents/research_agent.py` | Shared core + V1 YouTube source + `run_research(source=...)` |
| `pipeline/agents/instagram_source.py` | V2: Business Discovery + Hashtag Search, Reels filter, creator baseline, hashtag weekly limit |
| `pipeline/state.py` | `research_output` now also has `trend_type`, `trend_checks` and `growth_ratio` |
| `pipeline/.env.example` | `TREND_SOURCE`, Instagram variables, threshold overrides |
| `experiments/trend_e1/run_e1.py` | Runs both versions, writes summary, labels CSV, precision scoring |
| `experiments/trend_e1/niches.json` | Niches, creator lists, hashtags |

---

## 5. How each version collects data

### V1 YouTube

| Step | Detail |
|---|---|
| Search | `search.list` twice per query: last 14 days, and last 3 days. `order=viewCount` favours older videos, so the 3-day search keeps the growth check from going blind |
| Details | `videos.list` (views, likes, comments, duration ≤ 180 s), `channels.list` (subscribers) |
| Filters | Shorts only, ≥ 1,000 views, English, not hashtag-only titles, Latin script |
| Over-performance | `views ÷ max(subscribers, 1000)` |
| Text for clustering | cleaned title |
| Cost | ~1,010 quota units per fresh run (10,000/day free → ~9 runs/day). Cached 6 h, so a re-run costs ~15 |

### V2 Instagram

| Step | Detail |
|---|---|
| Business Discovery | For each creator in a list: followers + last 50 posts (caption, likes, comments, time, type) |
| Hashtag Search | `ig_hashtag_search` → `top_media` + `recent_media`. Posts have **no username**, so they add volume only and never count as a creator, for over-performance or for growth |
| Filters | Reels only, likes visible, last 14 days, informative English caption |
| Over-performance | post likes+comments ÷ **that creator's own median** likes+comments (their real "normal") |
| Text for clustering | first caption line |
| Views | Not available for other people's Reels, so likes+comments stand in for views |
| Limits | 30 *new* hashtags per 7 days per account (tracked locally); Business Discovery only works for Business/Creator accounts |
| Cost | free (~16 Graph API calls per niche) |

---

## 6. Experiment setup

| | |
|---|---|
| Date | 2026-11-18 |
| Niches | **motivation**: real creator profile from Module 1 (`creator_profile.json`). **fitness_beginners**: small profile written for the test |
| Queries | Generated once by the local LLM per niche, then **reused for both versions** |
| Motivation queries | motivational advice · personal growth tips · living fully tips · daily life hacks · motivational quotes |
| Fitness queries | home workout plan · beginner workout tips · muscle building tips · fat loss guide · workout motivation tips |
| V2 creators, motivation (15) | garyvee, jayshetty, melrobbins, tonyrobbins, lewishowes, simonsinek, robinsharma, edmylett, brendonburchard, davidgoggins, mattdavella, aliabdaal, thedankoe, jimkwik, marieforleo |
| V2 creators, fitness (16 of 20 tried) | jeffnippard, athleanx, jeremyethier, kayla_itsines, chloe_t, blogilates, whitneyysimmons, sam_sulek, chrisheria, mikethurston, thebodycoach, demibagby, krissycela, mrandmrsmuscle, heatherrobertsoncom, pamela_rf. *Personal accounts, skipped (code 110):* sydneycummingshoutz, noeldeyzel, michellelewin, jamesgrage |
| V2 hashtags (configured) | motivation, selfimprovement, personalgrowth, consistency, mindset / homeworkout, fitnesstips, gymbeginner, fatloss, workoutmotivation. **Blocked**, see section 7 |
| Labelling LLM | Ollama `qwen2.5:1.5b` (local) |
| Embeddings | `all-MiniLM-L6-v2` |

---

## 7. Instagram access setup (what was done, what went wrong)

The final working setup took several tries. It is recorded here because
anyone repeating it will hit the same problems.

| Step | What happened | Fix |
|---|---|---|
| Create app | "Create App" did not appear | The Facebook account first had to register as a Meta developer ("Get Started") |
| App type | The old "Business app type" screen no longer exists | Meta now asks for a **use case**. Choose the Instagram use case and use **"API setup with Facebook login"**, not "Instagram login" (Instagram login has no Business Discovery or Hashtag Search) |
| Token button | Explorer shows "Get Token" | Pick **Get User Access Token**, not Page token |
| `me/accounts` | Only old Pages, none with `instagram_business_account` | No Instagram was connected to any Page. A **new Instagram account (`viralhook`)** was made, switched to Creator, and connected to a new Facebook Page |
| `me/accounts` empty `[]` | The token had no Page access | Reset the app in Facebook → Business integrations, and add **`business_management`** (Pages created from Instagram go into a Business Portfolio) |
| `business_discovery` → `(#100) nonexisting field` | The query used the wrong ID (not the Instagram account's) | Use the `instagram_business_account` id (`17841…`) |
| `business_discovery` → `(#10) no permission` | Missing permission | Add **`instagram_manage_insights`** |
| ✅ Working | `garyvee` → 12.2M followers | Token extended to 60 days (valid until **2027-01-17**) |
| Hashtag Search → `(#10) …'Instagram Public Content Access'… must be reviewed` | Needs Meta **App Review** | Not possible in development mode. V2 ran with creators only |

**Final permissions:** `instagram_basic`, `instagram_manage_insights`,
`pages_show_list`, `pages_read_engagement`, `business_management`.

**Who does this:** only the developers, once. End users would just click
"Connect Instagram" (W2). Public users would require App Review and Business
Verification.

---

## 8. Results

### 8.1 Side by side

| | V1 motivation | V1 fitness | V2 motivation | V2 fitness |
|---|---|---|---|---|
| Posts fetched → usable | 385 → 131 | 440 → 239 | 750 → 201 Reels | 800 → 58 Reels |
| Distinct posts / clusters | 115 / 64 | 237 / 80 | 182 / 111 | 55 / 47 |
| Clusters left after creator-fit gate | 9 | 42 | 2 | **0** |
| trend / emerging / evergreen / topic | 0 / 0 / 3 / 5 | **3 / 1 / 15 / 18** | 0 / 0 / 0 / 2 | 0 / 0 / 0 / 0 |
| Recent share of sample (even rate = 0.21) | 0.37 | 0.37 | 0.34 | 0.14 |
| Cost | ~1,015 units fresh / 14 cached | ~1,015 / 16 | 16 calls, free | 17 calls, free |
| Time (s) | ~60–117 | ~50–93 | 49 | 29 |

### 8.2 V1 YouTube: motivation (top 5)

| # | Topic | Type | O G S R | Creators | Posts | Rel. growth | Outlier | Fit |
|---|---|---|---|---|---|---|---|---|
| 1 | Motivational Quotes | evergreen | ✓ ✗ ✓ ✓ | 6 | 6 | 0.17 | 69.3 | 0.53 |
| 2 | Tiny Habits That Upgrade Your Life | evergreen | ✓ ✗ ✓ ✓ | 4 | 4 | 0.69 | 3.7 | 0.50 |
| 3 | Smart Tips for Daily Life | evergreen | ✓ ✗ ✓ ✓ | 4 | 4 | 0.24 | 1.5 | 0.49 |
| 4 | Shahrukh Khan's Motivational Advice | topic | ✓ ✗ ✗ ✓ | 2 | 2 | 0.39 | 235.7 | 0.63 |
| 5 | DIY Everyday Solutions | topic | ✓ ✗ ✗ ✓ | 2 | 2 | 1.30 | 45.4 | 0.48 |

No `trend`. Motivation content is mostly evergreen (quotes, habits), so this is plausible.

### 8.3 V1 YouTube: fitness (top 5)

| # | Topic | Type | O G S R | Creators | Posts | Rel. growth | Outlier | Fit | First look |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Home Full Body Workout with Bands and Bar | trend | ✓ ✓ ✓ ✓ | 5 | 6 | 1.51 | 1.58 | 0.79 | partly right, mixes in "exercises for women" |
| 2 | Fitness Tips and Motivation | trend | ✓ ✓ ✓ ✓ | 4 | 4 | 1.44 | 1.51 | 0.82 | **wrong**: generic "subscribe" Shorts from 0–98-sub channels |
| 3 | Building Muscle After 60 | trend | ✓ ✓ ✓ ✓ | 6 | 7 | 1.91 | 1.62 | 0.59 | partly right, mixes in "high-protein foods" |
| 4 | Build a Stronger Body From Home | emerging | ✓ ✓ ✗ ✓ | 2 | 2 | 1.32 | 37.8 | 0.53 | – |
| 5 | Home Workout Tips for Athletic Fitness | evergreen | ✗ ✗ ✓ ✓ | 14 | 20 | 0.76 | 1.34 | 0.81 | correct: big, old, not growing |

### 8.4 V2 Instagram: motivation

| # | Topic | Type | O G S R | Creators | Posts | Fit |
|---|---|---|---|---|---|---|
| 1 | Stress Management Mindset | topic | ✓ ✗ ✗ ✓ | 2 (melrobbins, brendonburchard) | 2 | 0.51 |
| 2 | Measuring Life by Who You Get to Come Home To | topic | ✗ ✗ ✗ ✓ | 2 (lewishowes, brendonburchard) | 2 | 0.49 |

Two posts that happen to touch a similar idea. Not useful as trends.

### 8.5 V2 Instagram: fitness

**No trends.** All 47 clusters failed the creator-fit gate (fit < 0.45).

### 8.6 V2 creator data (why the sample is thin)

| | Motivation | Fitness |
|---|---|---|
| Creators reached | 15 / 15 | 16 / 16 |
| Creators with 0 Reels in the last 14 days | 4 (davidgoggins, mattdavella, thedankoe, jimkwik) | 4 (chloe_t, chrisheria, mikethurston, mrandmrsmuscle) |
| Most posts from one creator | garyvee 42 of 201 | kayla_itsines 13 of 58 |

---

## 9. Bugs found and fixed during the experiment

| # | Bug | How it showed | Fix |
|---|---|---|---|
| 1 | **The 3-day search over-samples recent uploads** | 37–42 % of YouTube posts were "recent" (even rate = 21 %). The first run called almost every cluster growing (ratio 1.5–2.2 everywhere) | Growth is measured relative to the whole niche |
| 2 | **Smoothing pulled small clusters toward "not growing"** | After fix 1, even a 3-of-3-recent cluster could not pass, because the +0.5 smoothing pulled it toward 1 while the niche ratio was not smoothed | Smoothing now pulls toward the *niche's* share (odds ratio, `relative_growth()`) |
| 3 | **The LLM gave different queries every run** | Results changed between runs and the cache missed (~1,000 quota units each time) | The runner reuses the day's queries for both versions (`--new-queries` to refresh) |
| 4 | **A failed hashtag still used a weekly slot** | Hashtag Search is blocked, but each attempt counted toward the 30/week limit | On an access error: stop trying hashtags, give slots back, continue with creators |

---

## 10. Analysis

### 10.1 What works (V1)

- **The definition separates topics sensibly.** "Home workout tips" (20 posts, 14 channels, 6–12 days old, not growing) is `evergreen`, not `trend`. The old code had no growth check and would have ranked it at or near the top.
- **No false "trends" in an evergreen niche.** In motivation, everything was evergreen or topic.
- **Over-performance flags real outliers.** E.g. Shahrukh Khan advice: 388K views on an 860-subscriber channel.
- **The cost is low:** ~1,015 units fresh, ~15 cached.

### 10.2 What is wrong or weak (V1)

| # | Problem | Example | Suggested fix |
|---|---|---|---|
| 1 | Tiny channels pass "overperforms" (`SUBSCRIBER_FLOOR = 1000`) | "Fitness Tips and Motivation" trend: 0–98 subs, 1–7K views | Raise the floor to ~5,000, or compare with each channel's own median views |
| 2 | Clusters mix nearby sub-topics | "After 60" + "protein foods"; "bands & bar" + "exercises for women" | `CLUSTER_DISTANCE_THRESHOLD` 0.6 → 0.5, then check on labels |
| 3 | Romanised non-English titles get through | "Jeevitha satyalu… inspiring quotes" (Telugu) | Title language detection (e.g. `langdetect`) |
| 4 | Growth comes from a search sample | biased sample, now corrected relatively | Daily snapshots of video stats (plan step 5) |

First look at the 3 fitness trends: **1 wrong, 2 partly right**. This is
the developer's judgement; the real precision will come from hand labels.

### 10.3 Why V2 failed

1. **No Hashtag Search.** It needs App Review ("Instagram Public Content Access"). This removed V2's only discovery channel beyond the fixed list.
2. **Captions don't name the topic.** YouTube titles are written for search ("5 Best Exercises to Build Muscle After 60"). Big Instagram creators write personal or promotional captions:
   - kayla_itsines: "South Africa… your AMAZING 🇿🇦"
   - blogilates: "My corporate girlies asked for work pants…"
   - garyvee: "Pls if you're under 30 watch this"

   So 182 posts made 111 clusters, and almost none fit the niche.
3. **A fixed set of 15 creators rarely overlaps.** Each big creator posts their own content, so "≥ 3 creators on one topic" almost never happens. YouTube search reaches ~150 channels per niche.
4. **The data is uneven:** 4 creators per niche had no Reels in 14 days, and one creator gave up to 22 % of all posts (kayla_itsines 13 of 58).

**Ablation tried:** embedding the full caption (300 characters) instead of the first
line, on the same cached data. It barely changed anything: still only 2
two-creator `topic`s per niche, e.g. "REVIVE is here!" and "you know what
I'm here to do". So the problem is the data, not the text processing.

### 10.4 What V2 does better

- **Better over-performance measure:** each creator's own median, not a subscriber proxy.
- **Unbiased growth sample:** full creator timelines (recent share 0.14–0.34), not a search that inflates recent posts (0.37–0.42).
- **Free**, with no daily quota.

These would matter if V2 had enough topical, overlapping data, which it doesn't today.

---

## 11. Tests

| Suite | Result |
|---|---|
| `tests/backend/test_research_agent.py` (core + V1) | **51 passed** |
| `tests/backend/test_instagram_source.py` (V2, fake Graph API) | **15 passed** |
| All of `tests/backend` | **164 passed.** `test_qdrant_store` and `test_multimodal_features` were not collected because `qdrant_client` is not installed locally (unrelated) |

Covered: all 4 checks and every `trend_type`, growth edge cases (0 old / 0
new posts), relative growth, ranking by type, `.env` overrides, both
YouTube search windows, unknown or unconfigured sources, Instagram parsing,
creator baseline, Reels filter, hidden likes, weekly hashtag limit, access-error
handling, personal-account skip, expired token, caching, and full
end-to-end runs for both sources.

---

## 12. Limitations of this experiment

- **One day, two niches.** The results are indicative, not statistically strong.
- **The "first look" judgements are by the developer.** Hand-labelled precision (`labels_2026-11-18.csv`) is still to be done.
- **V2 ran without Hashtag Search.** It is not the full V2 design.
- **V2 used big celebrity creators.** Mid-size creators (50K–500K) might post more on-topic Reels.
- **No forward check yet.** It is not yet known whether the "trend"s were still growing 7 days later.

---

## 13. Recommendation

1. **Make V1 YouTube the Research Agent's source** (it is already the default) and fix V1 problems 1–3.
2. **Keep V2 in the code** (`TREND_SOURCE=instagram`), but not as the default. The token already works for reading Instagram data, which is what W2 "past performance" (the creator's own posts) needs.
3. **Report it as a finding:** official Instagram access without App Review cannot support niche-wide trend detection. Business Discovery gives good per-creator data, but no topical discovery.

## 14. Next steps

1. Hand-label `results/labels_2026-11-18.csv` → `python experiments/trend_e1/run_e1.py --score experiments/trend_e1/results/labels_2026-11-18.csv`
2. Fix V1 problems 1–3, re-run with the same queries, compare before and after.
3. Re-run in 7 days for the forward check.
4. Optional V2 retry: 40–50 mid-size creators per niche.
5. Optional: apply for App Review (Public Content Access) if hashtags become important.

---

## 15. How to reproduce

```bash
# .env (root): YOUTUBE_API_KEY, IG_ACCESS_TOKEN, IG_USER_ID
python experiments/trend_e1/run_e1.py                         # both versions, all niches
python experiments/trend_e1/run_e1.py --versions youtube      # V1 only
python experiments/trend_e1/run_e1.py --new-queries           # fresh LLM queries
python -m pytest tests/backend/test_research_agent.py tests/backend/test_instagram_source.py
```

Outputs: `results/summary_<date>.md` (tables), `results/labels_<date>.csv`
(for hand labels), and `results/<date>_<version>_<niche>.json` (full output,
git-ignored because it contains other creators' captions).

The Instagram token is valid until **2027-01-17**. After that, generate a new
one in Graph API Explorer with the 5 permissions in section 7.
