# Trend E1 — first results (2026-11-18)

Status: **both versions tested live**, on two niches (motivation,
fitness_beginners), with the same queries for both. V2 ran with Business
Discovery only: Hashtag Search needs Meta App Review (see section 5). These
numbers come from one day, and the trend judgements below are a first look
by the developer, not the hand-labelled precision from the evaluation plan.

## 1. Tests

| Suite | Result |
|---|---|
| `tests/backend/test_research_agent.py` (core + V1) | 51 passed |
| `tests/backend/test_instagram_source.py` (V2, fake Graph API) | 15 passed |
| All of `tests/backend` | 164 passed. `test_qdrant_store` / `test_multimodal_features` not collected: `qdrant_client` is not installed locally (unrelated to this work) |

What the V2 tests cover: Business Discovery and Hashtag parsing, the
creator baseline (median likes+comments), the Reels-only filter, posts with
hidden likes, the 30-hashtags-per-week limit, a missing Hashtag Search permission
(the run stops trying hashtags, gives the weekly slots back and goes on with
creators), personal accounts being skipped, an expired token stopping the run,
caching, and the full `run_research(source="instagram")` producing a `trend`.

## 2. Side by side

| | V1 YouTube | | V2 Instagram | |
|---|---|---|---|---|
| | motivation | fitness | motivation | fitness |
| Posts in → usable | 385 → 131 | 440 → 239 | 750 → 201 Reels (15 creators) | 800 → 58 Reels (16 creators) |
| Clusters | 64 | 80 | 111 | 47 |
| trend / emerging / evergreen / topic | 0 / 0 / 3 / 5 | **3 / 1 / 15 / 18** | 0 / 0 / 0 / 2 | 0 / 0 / 0 / 0 |
| Recent share of sample (uniform = 0.21) | 0.42 | 0.37 | 0.34 | 0.14 |
| Cost | ~1,015 quota units fresh, ~15 cached | same | 16 Graph API calls, free | 17 calls, free |

Full tables with evidence links: `results/summary_2026-11-18.md`.

**Verdict for now: V1 (YouTube) is clearly better as the trend source.**
V2 found no trend in either niche, and its 2 "topics" are not useful (section 5).

## 3. What works (V1)

- **The trend definition separates topics that make sense.** "Home workout
  tips" (20 posts, 14 channels, mostly 6–12 days old, not growing) came out
  as `evergreen`, not `trend`. The old code had no growth check, so with
  14 channels and a fit of 0.81 it would have ranked at or near the top.
- **Motivation has no `trend`, only `evergreen`.** That fits the niche:
  quotes and habits content is always there.
- **A search bias was found and fixed.** The extra 3-day search makes 37–42 %
  of the YouTube sample "recent". An even upload rate over 14 days would give
  21 %, and Instagram's full creator timelines give 14–34 %. In the first
  version this made almost every YouTube cluster "growing" (growth 1.5–2.2
  everywhere). Growth is now measured *relative to the whole niche* (an odds
  ratio with smoothing toward the niche, in `relative_growth()`), so the bias
  cancels out.
- **Cost is fine.** About 1,015 units for a fresh run (≈ 9 runs/day on the
  free quota). A same-day re-run with the same queries costs about 15.

## 4. What is wrong or weak (V1)

| # | Problem | Example from this run | Suggested fix |
|---|---|---|---|
| 1 | **Tiny channels pass "over-performs".** `SUBSCRIBER_FLOOR = 1000` means a 0-subscriber channel with 1,500 views scores 1.5× | Fitness trend "Fitness and Motivation Tips": generic "subscribe / transform your body" Shorts from channels with 0–98 subs and 1–7K views. **Not a real trend.** | Raise the floor (e.g. 5,000), or use the channel's own median views (plan step 4) |
| 2 | **Clusters mix nearby sub-topics** | "Muscle growth after 60" mixes "exercises after 60" with "high-protein foods". "Home band & bar workouts" mixes in "exercises for women" | Lower `CLUSTER_DISTANCE_THRESHOLD` (0.6 → 0.5) and check on labels |
| 3 | **Romanised non-English titles get through** | "Jeevitha satyalu… inspiring quotes" (Telugu) in Motivational Quotes | Language detection on the title (e.g. `langdetect`) |
| 4 | **Different queries on every run** (LLM) | Each fresh run returned a different set of 5 queries | The runner reuses the day's queries; for the report, fix them per niche |
| 5 | **Growth is an estimate from a search sample, not a measurement** | the sample is biased, now corrected relatively | Daily snapshots (plan step 5) |

First look at the 3 fitness `trend`s: 1 wrong, 2 partly right (real growing
themes, but mixed clusters). The real precision number will come from the
hand labels.

## 5. V2 Instagram, live: what happened and why

**Setup worked.** The token (5 permissions, valid until 2027-01-17) reached
all 15 motivation creators and 16 of 20 fitness candidates (4 are personal
accounts, code 110).

**Hashtag Search is blocked.** Meta answers `(#10) To use 'Instagram Public
Content Access', your use of this endpoint must be reviewed and approved`.
In development mode the app gets Business Discovery but not Hashtag Search.
Getting it means App Review, usually with Business Verification. So V2 ran
on the creator lists only.

**Why V2 found nothing useful:**

1. **Captions don't say the topic.** Big creators write personal or
   promotional captions: Kayla Itsines "South Africa… your AMAZING",
   Blogilates selling work pants, Garyvee "Pls if you're under 30 watch
   this". YouTube Shorts titles are written for search ("5 Best Exercises
   to Build Muscle After 60"). With topic-free text, 182 posts made 111
   clusters, and almost none passed the creator-fit gate (motivation 111 → 2,
   fitness 47 → 0).
2. **A fixed list of 15 creators rarely overlaps.** Each big creator posts
   their own content. "Spreading" (≥ 3 creators on one topic) almost never
   happens in a set this small. YouTube search instead pulls ~150 different
   channels on the same query.
3. **The data is uneven.** In fitness, 4 of 16 creators had 0 Reels in the last
   14 days, and Kayla Itsines alone had 13 of 58. In motivation, Garyvee
   had 42 of 201.
4. **Embedding the full caption (300 chars) instead of the first line did
   not fix it** (tried on the same cached data): still only 2 two-creator
   `topic`s per niche, e.g. "REVIVE is here!", "you know what I'm here to do".

**What V2 does better:** over-performance against each creator's own median,
and an unbiased growth sample (full timelines: recent share 0.14–0.34, not the
search-inflated 0.37–0.42). If Hashtag Search becomes available, or the
list is 50+ mid-size niche creators, V2 may become useful. As it stands, it is not.

## 6. Recommendation

1. **Use V1 (YouTube) as the Research Agent's source** and fix V1 problems
   1–3 next.
2. **Keep V2 in the code** (`TREND_SOURCE=instagram`), but as an experiment
   and for later, not the default. Its real value will be the creator's
   *own* Instagram history (W2 "past performance"), which this token can
   already read.
3. For the FYP report this is a useful negative result: official Instagram
   access without App Review cannot support niche-wide trend detection, and
   the experiment shows why with numbers.

## 7. Next steps

1. Hand-label `results/labels_2026-11-18.csv` and run `--score` to get precision.
2. Fix V1 problems 1–3, re-run with the same queries, and compare.
3. Re-run after 7 days for the forward check.
4. Optional V2 retry: 40–50 *mid-size* creators (50K–500K followers) per niche,
   who post more on-topic Reels.
