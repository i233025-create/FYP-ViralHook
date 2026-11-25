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

---

# Update (2026-11-22): V1 fixes 1–3 and re-run

## 8. What changed

| # | Problem (section 4) | Fix | Setting |
|---|---|---|---|
| 1 | Tiny channels pass "over-performs" | `SUBSCRIBER_FLOOR` 1000 → 5000: a 0-sub channel now needs 7,500+ views for 1.5× | `TREND_SUBSCRIBER_FLOOR` |
| 2 | Clusters mix nearby sub-topics | `CLUSTER_DISTANCE_THRESHOLD` 0.6 → 0.5 | `TREND_CLUSTER_DISTANCE` |
| 3 | Romanised non-English titles | Title dropped if < 60 % of its words are common English words (`wordfreq`, Zipf ≥ 3) | `TREND_MIN_ENGLISH_WORD_SHARE` |

`langdetect` (suggested in section 4) was tried first and rejected: on short
titles it called "Train Smarter, Build Stronger!" German and the Telugu title
English. On the E1 titles the word-share check gave English ≥ 0.67 and
Hinglish/Telugu/Spanish ≤ 0.57.

Tests: 174 passed in `tests/backend` (qdrant tests not collected, as before).

## 9. Results

**Re-run with the same queries** (`run_e1.py --versions youtube --queries-from 2026-11-18`,
`results/summary_2026-11-22.md`): motivation 0 trend / 2 evergreen / 1 topic,
fitness 0 trend / 17 evergreen / 23 topic. Fitness went from 3 `trend`s (18 Nov) to 0.

**That drop is the data, not the fixes.** `ablation_fixes.py` runs every
setting on the *same* data pull (`results/ablation_2026-11-22.md`): with the
**old** settings, today's fitness data also gives 0 `trend`s. Four days later
the queries return different videos, so 18 Nov vs 22 Nov is not a fair
before/after on its own.

Effect of each fix on the same data:

| Fix | motivation | fitness |
|---|---|---|
| 1 floor | Same clusters; low outliers drop further (e.g. "Living Life Fully" 1.3 → 0.3), so small channels can no longer pass "over-performs" | Outliers of the top topics fall (e.g. "Beginner Gym Tips" 2.4 → 0.6) because their channels are under 5K subs |
| 2 cluster 0.5 | 65 → 77 clusters | 70 → 101 clusters; the 12-channel "Home fitness and quick exercises" mix splits into "3 day home routine", "abs", "belly fat", … |
| 3 English | 126 → 120 posts | 215 → 208 posts |

Fix 3, all 13 titles it removed (none English): "Akshay Kumar ka bayan",
"BiggBoss Marathi … Motivational SpeechMarathi" (×2), "samay nikalkar jarur
padhe", "Apna Mahaul Badlo", "Jeevitha satyalu…", "Body Kaise Banaye bina gym
ke?", "Creatine Kab Lena Chahiye?", "Sek palh har zia hi" (Mizo), "Gym Shuru
Karne Se Pehle Ye 5 Baatein…", "Yeh Basic Gym Math Nahi Aata…", "Gym Mein Hero
Banne Ke Chakkar Mein…", "Asli Dost, Asli Motivation!".

Note on motivation: with fix 3 alone, "Motivational Quotes" (4 creators)
became a `trend`. With fix 2 as well it splits into two `evergreen` quote
clusters. That `trend` was a mixed cluster, so splitting it is the intended effect.

## 10. Still open

- **Not caught by fix 3:** an English title over non-English content ("new
  training motivation quotes in hindi" is top evidence for motivation #1). That
  needs the audio/transcript language, not the title.
- **Too few `trend`s to measure precision.** 0 in both niches today. To get a
  real number: label `results/labels_2026-11-22.csv` (8 rows) with
  `labels_2026-11-18.csv`, and add more niches or run on more days.
- The forward check (7 days after 18 Nov = 25 Nov): done, see section 11.

---

# Update (2026-11-25): forward check, labels, language-name filter

## 11. Forward check (18 Nov → 25 Nov)

Same queries, fresh data (`run_e1.py --versions youtube --queries-from 2026-11-18`,
`results/summary_2026-11-25_forward.md`): motivation 0 trend / 1 evergreen / 1 topic,
fitness 0 trend / 1 emerging / 12 evergreen / 25 topic.

`forward_check.py --from 2026-11-18` looks up every topic shown on 18 Nov
in the 25 Nov data (a video matches when its title embedding has cosine ≥ 0.6
with the centroid of the topic's 18 Nov evidence;
`results/forward_2026-11-18_to_2026-11-25.md`):

| 18 Nov topic | Type then | Creators then → now | Verdict |
|---|---|---|---|
| Home Full Body Workout with Bands and Bar | trend | 5 → 25 | grew |
| Fitness Tips and Motivation | trend | 4 → 5 | grew (slightly) |
| Building Muscle After 60 | trend | 6 → 5 | about the same |
| Build a Stronger Body From Home | emerging | 2 → 2 | about the same |
| Home Workout Tips for Athletic Fitness | evergreen | 14 → 30 | grew |
| Motivational Quotes | evergreen | 6 → 4 | faded |
| Tiny Habits / Smart Tips (motivation) | evergreen | 4 → 3 | about the same |
| SRK advice / DIY (motivation) | topic | 2 → 1 | faded |

**Reading:** the forward check does *not* separate `trend` from `evergreen`:
the evergreen "home workout" topic grew as much as the band-and-bar `trend`.
Both centroids are generic "home workout" titles, so they match a large share
of any fitness pull. The match counts measure "this kind of content is still
everywhere", not "this specific trend took off". A fair forward check needs
daily snapshots of the same videos' view counts (plan step 5), not re-matching
titles.

## 12. Labels and precision

`labels_2026-11-18.csv` (12 rows) and `labels_2026-11-22.csv` (8 rows) now
have labels. **They are draft labels written by Claude from the evidence
titles, channel sizes and view counts, marked `draft (Claude, check)` in
`notes`. The developer must open the links and confirm them before the
numbers go in the FYP report.**

Every shown row came out `not_trend`, so precision@k = **0.00** (V1: 10 + 8
rows, V2: 2 rows). By type: the 3 `trend`s of 18 Nov are all `not_trend`
(mixed clusters from 0–98-subscriber channels, or one creator's series). The
evergreen/topic rows are real recurring content but not trends, which is what
their type already says. So the `trend` check is too loose and the other types
are right.

## 13. Fix 4: titles that name another language

Section 10 noted that English titles over non-English content got through
("new training motivation quotes in hindi", and on 22 Nov also "motivational
quotes Kannada #kannada"). A video is now dropped when its title, a hashtag
(including word starts like `#hindimotivation`) or a tag names a non-English
language (`NON_ENGLISH_LANGUAGE_WORDS`, `names_other_language()`).
On the 25 Nov data it removed 5 of 111 motivation videos (4 × "Daily tips in
hindi", 1 × "Islamic motivational quotes … in Urdu") and 0 of 196 fitness videos.
6 new tests; `tests/backend`: 194 passed. `test_qdrant_store` and
`test_module1_llm` were not collected (`qdrant_client` and `langchain_core` are
not installed on this machine), and `test_multimodal_features::test_extract_shot_features_on_real_video`
fails on a missing `scene_detector` dependency (unrelated to this work).

Still not caught: Hindi content whose title is English and names no language
("apj abdul kalam motivation quote", "premanand maharaj ji motivational
speech"). That needs the transcript language.

## 14. Final state of E1

1. **Source:** V1 YouTube. V2 Instagram stays as an experiment (section 5).
2. **What works:** the four-check definition puts recurring content in
   `evergreen` and not `trend`, the relative-growth correction, and the
   filters for floor, clustering and language.
3. **What doesn't:** precision of `trend` is 0/3 (draft labels), and in 3
   later runs no `trend` passed. The current checks cannot confirm a real trend
   from a single 14-day search sample.
4. **Next (outside E1):** daily view snapshots for true growth, and the
   developer checking the draft labels.

---

# Update (2026-11-25, later): channel baseline, measured growth, 4 niches

The three weak points from section 14 are now addressed. All of this is YouTube only.

## 15. What changed

| # | Weak point | Change | Where |
|---|---|---|---|
| 5 | "Over-performs" compares views with subscribers, so tiny channels pass | Outlier = views ÷ max(**the channel's own median Shorts views**, 5,000). The median uses the channel's latest 30 uploads (only Shorts, ≥ 3 days old, not in this run), cached for a week. Channels with < 5 such Shorts fall back to subscribers | `_fetch_channel_baselines()`, `TREND_CHANNEL_BASELINE`, `TREND_VIEW_BASELINE_FLOOR` |
| 6 | "Growing" is guessed from one search sample | **Daily view snapshots.** Each run stores every video's views and re-reads the videos tracked over the last 8 days. Next day: acceleration = views/day since the last snapshot ÷ the video's lifetime views/day. A cluster is growing when its median acceleration ÷ the niche's is ≥ 1.3 | `pipeline/agents/trend_snapshots.py`, `_apply_snapshots()` |
| 7 | `trend` with estimated growth was wrong 3/3 times | A cluster that passes all four checks with **estimated** growth is only `emerging`. `trend` needs measured growth (≥ 2 posts with an earlier snapshot). Instagram is not affected (it has no snapshots) | `TREND_REQUIRE_MEASURED_GROWTH` |
| 8 | Mixed-script titles ("Motivation नहीं, Discipline…", 78 % Latin) | Dropped when the title has > 1 letter from a non-Latin script | `MAX_NON_LATIN_LETTERS` |
| 9 | Different queries per run; 2 niches only | Fixed `queries` per niche in `niches.json`. Added `tech_reviews` and `quick_recipes`. In motivation, "daily life hacks" and "living fully tips" were replaced: they pulled off-niche lifehack videos | `niches.json`, `run_e1.py` |

Tests: 212 passed in `tests/backend` (19 new in `test_trend_snapshots.py` and
`test_research_agent.py`). Not collected/failing for reasons unrelated to this
work, as in section 13: `test_qdrant_store`, `test_module1_llm`,
`test_multimodal_features::test_extract_shot_features_on_real_video`.

## 16. Day 0 (25 Nov), 4 niches (`results/summary_2026-11-25.md`)

| Niche | Usable | Channel baselines | Types (T/E/Ev/Top) | Shown |
|---|---|---|---|---|
| motivation | 141 | 87 / 98 channels | 0/0/2/1 | 2 evergreen, 1 topic |
| fitness_beginners | 197 | 139 / 155 | 0/2/11/26 | 2 emerging, 3 evergreen |
| tech_reviews | 129 | 115 / 122 | 0/0/4/4 | 4 evergreen, 1 topic |
| quick_recipes | 213 | 168 / 174 | 0/5/13/27 | 5 emerging |

- **No `trend` on day 0, by design.** No niche has a snapshot older than
  20 hours yet. In quick_recipes, 4 clusters passed all four checks on
  estimated growth and were held at `emerging`. Under the old rules they
  would have been called `trend`.
- **Channel baselines reach 85–97 % of channels.** Cold-cache cost was about
  180–260 units per niche, on top of the ~1,000 for searches. For the next
  7 days the cache is warm.
- Same-day re-runs cost 16–19 units per niche and measure nothing (the
  20-hour gap rule), as intended.

## 17. Still open

- **Measured growth is only testable from tomorrow (26 Nov).** Run
  `run_e1.py --versions youtube` once a day. From day 2 the summary shows
  `(measured)` growth. A real precision number needs about a week of daily
  runs plus hand labels of the shown topics.
- **Hindi content with English titles and no language word** still passes
  (e.g. "Dr Apj Abdul kalam motivational video", "premanand ji speech"). This
  needs the transcript language.
- **Labels for 25 Nov are not filled in.** `labels_2026-11-18/22.csv` hold
  draft labels by Claude (section 12). They need checking by the developer.
- The local LLM was off, so topic names are cleaned top titles.

---

# Update (2026-11-25, evening): Urdu and Roman Urdu

## 18. What changed

| Part | Change |
|---|---|
| Language detection | `title_language()` returns `en` / `ur` (Urdu script) / `roman_ur` / `other`. Urdu vs Arabic (one script): letters only Urdu uses (ٹ ڈ ڑ ں ے ھ ہ), or Urdu-style ی ک گ چ پ with no Arabic-only letter (ة ي ك ى أ إ). Roman Urdu: ≥ 2 common Roman Urdu words, and either ≥ 60 % of words are English/Roman Urdu or ≥ 30 % are Roman Urdu, and the title is not plainly English (English-word share < 0.8). Hindi vocabulary (jeevan, safalta, pravachan, maharaj, shri…) → `other` |
| Filters | `_is_usable(video, languages)`. English niches unchanged. Urdu niches keep en/ur/roman_ur. "in Urdu" is allowed, "in Hindi" still dropped. A YouTube `hi` tag is accepted only when the title is Urdu / Roman Urdu |
| Search | `queries_ur` (2 per niche) with `relevanceLanguage=ur`, about 400 units per niche |
| Embeddings | Urdu niches use `paraphrase-multilingual-MiniLM-L12-v2` (Urdu ↔ English cosine 0.79 on a test pair, unrelated ≈ 0) |
| Thresholds | `calibrate_multilingual.py`: the same English titles embedded by both models. The cluster count matches the English model at distance 0.42–0.44 in all 4 niches → **0.44**. The creator-fit gate keeps the same share of clusters at 0.48–0.56 → **0.50** (`results/calibration_multilingual_2026-11-25.md`) |

Tests: 243 passed in `tests/backend` (33 new in `test_urdu_language.py`).

## 19. Result on 25 Nov data (`results/summary_2026-11-25.md`)

| Niche | Usable (before → with Urdu) | en / ur / roman_ur |
|---|---|---|
| motivation | 141 → 206 | 156 / 6 / 44 |
| fitness_beginners | 197 → 277 | 220 / 0 / 57 |
| tech_reviews | 129 → 149 | 134 / 0 / 15 |
| quick_recipes | 213 → 319 | 258 / 2 / 59 |

- Urdu-script Shorts are rare (0–6 per niche). Almost all Urdu content on
  YouTube Shorts is Roman Urdu.
- The multilingual model puts Urdu and English titles on one topic into one
  cluster (e.g. "ghar par body banaye" with "workout at home").
- Urdu-majority clusters exist (motivation 2, fitness 7, tech 1) but rank
  lower: they are `topic` / `evergreen`, and English posts are 75–85 % of
  each pull. A niche with `"languages": ["ur"]` shows only Urdu trends.
- Limit: Roman Urdu and Roman Hindi are the same language in Latin letters.
  Only Hindi-specific words keep Roman Hindi out, so Indian Roman-script
  content ("Crispy Masala Dosa… Ghar Par Banaye") also comes in.
