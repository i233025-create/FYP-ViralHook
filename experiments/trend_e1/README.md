# Trend E1 — YouTube (V1) vs Instagram (V2) as the research source

Which data source gives the Research Agent better trends for a creator?

| | V1 YouTube | V2 Instagram |
|---|---|---|
| Discovery | YouTube search (last 14 days + extra last-3-days search) | Hashtag Search (top + recent media) |
| Creator data | from the search results themselves | Business Discovery on a hand-picked list of 15–30 niche creators |
| Over-performs | views ÷ max(subscribers, 1000) | likes+comments ÷ the creator's own median likes+comments |
| Growing / Spreading / Recent | ✓ | ✓, but only from Business Discovery posts (hashtag posts have no author) |
| Cost | ~1,010 of 10,000 free quota units / run | free (Graph API calls) |
| Scope | all of YouTube Shorts search | only the listed creators + hashtags |

Everything after data collection is shared: same queries, scoring, clustering,
creator-fit gate and trend definition (`trend` / `emerging` / `evergreen` /
`topic`). Only the source changes, so the comparison is fair. The code is in
`pipeline/agents/research_agent.py` (core + V1) and
`pipeline/agents/instagram_source.py` (V2).

## Run

```bash
# both versions, every niche in niches.json
python experiments/trend_e1/run_e1.py

# one version / one niche
python experiments/trend_e1/run_e1.py --versions youtube --niches motivation
```

Re-runs on the same day reuse that day's queries, so the two versions see
the same queries and YouTube results come from the 6-hour cache (~15 quota
units instead of ~1,010). Pass `--new-queries` to ask the LLM again.

Outputs in `results/`:

- `summary_<date>.md`: side-by-side table, plus each version's top-5 trends with the 4 checks.
- `labels_<date>.csv`: one row per shown trend. Fill `label` with `trend` or `not_trend` after opening the evidence links.
- `<date>_<version>_<niche>.json`: full output. Git-ignored, because it holds other creators' captions.

After labelling:

```bash
python experiments/trend_e1/run_e1.py --score experiments/trend_e1/results/labels_<date>.csv
```

This prints precision per version and per trend_type, and appends it to the summary.

## V2 setup (one time, about 30 minutes)

1. developers.facebook.com: create an app of type **Business** and add the **Instagram Graph API** (Facebook Login) product. Development mode is enough, so no app review is needed.
2. Switch your own Instagram to a **Professional (Creator/Business)** account and link it to a Facebook Page.
3. Graph API Explorer: **Get User Access Token** with `instagram_basic`, `instagram_manage_insights`, `pages_show_list`, `pages_read_engagement` and `business_management` (add them to the app's Instagram use case, "API setup with Facebook login", first). Without `instagram_manage_insights`, Business Discovery fails with error code 10. Exchange it for a 60-day long-lived token.
4. `GET /me/accounts?fields=instagram_business_account` gives the id for `IG_USER_ID`.
5. Put `IG_ACCESS_TOKEN` and `IG_USER_ID` in `.env`. Check the creator lists in `niches.json`: they are starter lists, and personal accounts are skipped and reported in the summary.

**Hashtag Search does not work in development mode.** It needs the
"Instagram Public Content Access" feature, which requires App Review. Without it
the run skips hashtags and uses the creator list only (tested 2026-11-18).

Limits to keep in mind: 30 *new* hashtags per 7 days per account (tracked
in `pipeline/cache/ig_hashtag_usage.json`), and Business Discovery works
only for Business/Creator accounts.

## Evaluation plan

1. **Hand labels** (precision@5): label every shown trend as trend / not_trend from its evidence.
2. **Definition check**: on the labelled rows, compare `trend_type == "trend"` with the human label.
3. **Forward check**: re-run 7 days later and see whether the "trend" topics are still there or grew.
4. **Cost and coverage**: quota/calls, usable posts, creators reached (in the summary table).

## Fix ablation

`python experiments/trend_e1/ablation_fixes.py --queries-from 2026-11-18` runs
the YouTube agent with old settings, each V1 fix alone, and all fixes, on one
shared data pull (searches from cache, details fetched once, ~30 quota units).
Output: `results/ablation_<date>.md`.

## Forward check

`python experiments/trend_e1/forward_check.py --from 2026-11-18` looks up
every topic shown on that day in today's data (same queries; run `run_e1.py
--queries-from <day>` first, so the searches are cached). Output:
`results/forward_<day>_to_<today>.md`.

## Daily runs (measured growth)

Every YouTube run stores each video's view count in
`pipeline/cache/snapshots/<niche>/<date>.json` (git-ignored) and re-reads
the views of the videos it tracked over the last 8 days. From the second day
on, "growing" is **measured**: how fast a cluster's videos gain views now,
against their own lifetime pace, compared with the whole niche
(`trend_snapshots.py`). Until a niche has a snapshot that is at least 20 hours
old, growth is only an estimate and nothing is called a `trend`; the best a
cluster can get is `emerging`.

So run once a day, with the fixed queries from `niches.json`:

```bash
python experiments/trend_e1/run_e1.py --versions youtube
```

4 niches cost about 4,500–5,200 of the 10,000 daily quota units. The first
day costs more, because channel baselines are fetched and then cached for a
week. The summary shows, per topic, whether its growth is `measured` or an
`estimate`. `labels_<date>.csv` has a `growth_source` column.

On the developer's laptop this runs as the Windows scheduled task
**"FYP Trend Daily"** (every day at 13:00, or as soon as the laptop is on
after a missed run) via `daily_run.cmd`. Log: `pipeline/cache/daily_run.log`.
Remove it with `schtasks /Delete /TN "FYP Trend Daily" /F`.

## Urdu and Roman Urdu

Each niche in `niches.json` has `"languages": ["en", "ur"]` and two
`queries_ur`, which are searched with `relevanceLanguage=ur`. With `ur` on:

- Kept: English, Urdu script (zindagi badalne wali baatein in Urdu letters), and
  Roman Urdu ("Zindagi badal degi ye baat suno").
- Dropped: Arabic (same script as Urdu; told apart by letters only Urdu uses,
  such as ٹ ڈ ڑ ں ے, and letters only Arabic uses, such as ة ي ك ى), Devanagari,
  Roman Hindi with clearly Hindi vocabulary (jeevan, safalta, pravachan…),
  and other languages.
- YouTube tags a lot of Pakistani Roman Urdu content `hi`. In Urdu niches such
  a video is kept when its title is Urdu or Roman Urdu.
- Clustering uses `paraphrase-multilingual-MiniLM-L12-v2`, so an Urdu title and
  an English one on the same topic land in the same cluster. Its thresholds
  (distance 0.44, creator_fit 0.50) come from
  `calibrate_multilingual.py` (`results/calibration_multilingual_<date>.md`).

`"languages": ["ur"]` keeps only Urdu and Roman Urdu, so it shows only Urdu
trends. The extra cost is ~400 quota units per niche per day.
