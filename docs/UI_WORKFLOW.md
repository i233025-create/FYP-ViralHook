# ViralHook — UI Workflow & Design Brief

> **Purpose of this file:** a complete brief to hand to a designer (or Claude
> on claude.ai) to design the full ViralHook product UI. It describes every
> screen, what it shows, what the user can do, and every state (loading,
> empty, error, out of credits). Screens marked **[EXISTING]** are built
> today (`frontend_extracted/frontend/src/screens/…`); **[CHANGED]** exist but
> need new content; **[NEW]** do not exist yet.
>
> Last updated: 2026-11-08.

---

## 1. Product in one paragraph

ViralHook is an AI content studio for short-form video creators (Instagram
Reels first). A creator connects their Instagram account; ViralHook learns
their style from their own past reels (how they talk, their hooks, their
pacing, their look). It then helps them pick a topic (their own idea, checked
against real trend data, or a trending topic in their niche), writes 3 script
variants in **their own voice** with measured quality scores, turns the chosen
script into a scene-by-scene production plan, and outputs either an editable
Adobe Premiere Pro project (XML) or an AI-rendered video, which can be
published or scheduled to Instagram. It is sold as a subscription (Free /
Creator / Pro) with monthly credits.

**Target users:** Pakistani and international short-form creators, from
beginners to established creators; later, small agencies managing several
creators. Many speak a mix of Urdu and English.

## 2. Design principles (must-haves)

1. **Honest numbers.** Every score comes from a measurement, never invented.
   When something can't be measured, the UI shows `—` / "not enough data" /
   "low confidence" — never a fake number. Every score has a small **ⓘ "How is
   this measured?"** popover (texts in §7).
2. **The creator decides.** Research and scores inform; they never block. Low
   demand or a low score shows a warning, but the user can always continue.
3. **One clear next step.** The main flow is linear (Idea → Script → Plan →
   Output → Publish). Each screen has one primary button.
4. **Long jobs are visible and resumable.** Profile building, research,
   script generation and especially video rendering take seconds to minutes
   (renders run on a GPU queue). Show step-by-step progress, allow leaving the
   page, and surface finished jobs in a job tray / notifications.
5. **Credits are transparent.** Before any action that costs a credit, show
   the cost ("Uses 1 render credit · 7 left"). Never surprise-charge.
6. **Bilingual-friendly.** Content can be English or Roman Urdu; layouts must
   handle long code-mixed text. UI chrome is English.
7. **Responsive.** Desktop-first (creators edit on laptops) but every screen
   must work on a phone (≥ 360 px).

## 3. Current visual language (keep or evolve)

The current UI is a **Discord-like dark theme**: left sidebar + top header bar
+ scrolling content area, rounded cards, Inter font, lucide-react icons.

| Token | Hex | Use |
|---|---|---|
| bg | `#313338` | page background |
| sidebar | `#2B2D31` | sidebar, cards |
| dark / input | `#1E1F22` | inputs, wells |
| hover / active | `#35373C` / `#404249` | hover, selected rows |
| text / muted / faint | `#DBDEE1` / `#80848E` / `#4E5058` | text hierarchy |
| blurple (primary) | `#5865F2` (hover `#4752C4`) | primary buttons, active nav |
| green / yellow / red | `#23A55A` / `#F0B232` / `#F23F43` | good / medium / bad, success / warning / error |
| link | `#00A8FC` | links, XML option accent |

Score colouring today: ≥ 85 green, ≥ 70 yellow, otherwise muted.
Scene segments have colour badges (HOOK blurple, SETUP green, MAIN POINT
yellow, EVIDENCE red, CONCLUSION/CTA purple, …).

**Designer freedom:** a new brand identity is welcome, but the product needs
a light **and** dark theme, and the score/segment colour meanings above must
stay consistent.

## 4. Global layout

```
┌──────────────┬───────────────────────────────────────────────┐
│ ⚡ ViralHook  │ # Screen title · current topic      [jobs] [👤] │
│ AI Content   ├───────────────────────────────────────────────┤
│ Studio       │                                               │
├──────────────┤                                               │
│ (avatar)     │              page content                     │
│ @handle      │                                               │
│ niche · PLAN │                                               │
├──────────────┤                                               │
│ WORKFLOW     │                                               │
│ ▸ Dashboard  │                                               │
│ ▸ Ideation   │                                               │
│ ▸ Script   🔒│                                               │
│ ▸ Production🔒│                                              │
│ ▸ Export/Video🔒│                                            │
│ ▸ Publish  🔒│                                               │
│ LIBRARY [NEW]│                                               │
│ ▸ My content │                                               │
│ ▸ Scheduled  │                                               │
├──────────────┤                                               │
│ Credits [NEW]│                                               │
│ ███░ 7/10 renders                                            │
│ [Upgrade]    │                                               │
│ ⚙ Settings   │                                               │
│ ⎋ Sign out   │                                               │
└──────────────┴───────────────────────────────────────────────┘
```

- **Sidebar [CHANGED]:** brand, creator card (avatar, @handle, niche, **plan
  badge** [NEW]), workflow nav with lock icons (a step unlocks when the
  previous one is done: Dashboard/Ideation need a profile; Script needs a
  topic; Production needs a chosen variant; Export and Publish need a plan),
  **Library** section [NEW], **credits meter + Upgrade** [NEW], Settings [NEW],
  Sign out. On mobile it collapses to a drawer.
- **Header bar [CHANGED]:** `#` + screen title, and the selected topic on
  workflow screens. **[NEW]:** job tray icon (running/finished jobs with
  progress) and avatar menu (Settings, Billing, Sign out).
- Screens without the shell: Landing, Pricing, Auth, Onboarding.

## 5. User flows (overview)

```
Landing ─► Pricing ─► Sign up / Log in
                          │
                          ▼
          Onboarding: Connect Instagram ──(or)── Upload videos ──(or)── New creator
                          │
                          ▼
              Profile building (progress) ─► Profile result
                          │
                          ▼
                     Dashboard ◄──────────────────────────────────┐
                          │ "Create new video"                    │
                          ▼                                       │
        Ideation: ┌ Own idea ─► [Check my idea] ─► Idea report     │
                  │              (demand · saturation · fit ·     │
                  │               angles · similar trends)        │
                  └ Find trending ideas ─► Trend list              │
                          │ pick topic                            │
                          ▼                                       │
                 Topic confirmation ─► Script variants (A/B/C)     │
                          │ choose + edit                         │
                          ▼                                       │
                   Production plan (scenes, editable)             │
                          │                                       │
                          ▼                                       │
          Output choice ─► XML export (download)                  │
                        └► AI video: photos step ─► render queue   │
                                      ─► preview/edit             │
                          │                                       │
                          ▼                                       │
         Publish: publish now / schedule to Instagram ────────────┘
```

Billing touchpoints anywhere: credit cost shown before costly actions;
**Out of credits** modal → Upgrade → Checkout (provider page) → success →
back to where the user was.

---

## 6. Screen-by-screen specification

### 6.1 Landing page — [NEW]
Public marketing page.
- Hero: one-line value proposition ("Scripts and videos in your own voice"),
  primary CTA "Start free", secondary "See pricing".
- How it works: 4 steps (Connect Instagram → We learn your style → Pick an
  idea → Get scripts & video).
- Proof section: what is measured (style match, timing, hook, trend data from
  real videos) — honest, no fake testimonials or fake user counts.
- Pricing preview (links to Pricing), FAQ, footer (terms, privacy — needed for
  Meta app review).

### 6.2 Pricing — [NEW]
Three plan cards + monthly/yearly toggle + PKR/USD switch.

| | Free | Creator | Pro |
|---|---|---|---|
| Scripts / month | 5 | 50 | unlimited (fair use) |
| AI video renders / month | 0 (XML export only) | 10 | 40 |
| Research runs ("Check my idea", trend search) / month | 3 | 30 | 100 |
| Creator photo library + personalised video | — | ✓ | ✓ |
| Instagram publish | — | publish | publish + schedule |
| Creator profiles | 1 | 1 | 3 |

(Prices TBD — design with placeholders.) "Current plan" state for logged-in
users; feature comparison table below the cards; FAQ (what is a credit, do
credits roll over, cancel anytime).

### 6.3 Auth — [CHANGED] (exists as a mock: `screens/auth/AuthScreen.jsx`)
Today: one card with login/sign-up toggle (name, email, password), demo
credentials prefilled. Needed:
- **Sign up:** name, email, password (strength hint), accept terms; "Continue
  with Google" (later phase — design the button).
- **Log in:** email, password, "Forgot password?".
- **Forgot / reset password** screens; **verify email** notice.
- States: loading button, inline field errors, "email already registered",
  "wrong email or password", rate-limited ("too many attempts, try again in
  N minutes").
- Remove the prefilled demo credentials.

### 6.4 Onboarding — creator type — [CHANGED] (`CreatorTypeScreen.jsx`)
Today: "What kind of creator are you?" with two cards — **New Creator**
("I'm just getting started") and **Experienced Creator** ("I have existing
content"). Needed: make **Connect Instagram** the primary path:
1. **Connect Instagram (recommended)** — "We import your reels and captions
   automatically." Note: needs a Business or Creator account (link: how to
   switch, free, 1 minute).
2. **Upload videos instead** — the existing upload flow (fallback).
3. **I'm new / no videos yet** — the existing new-creator form.

### 6.5 Connect Instagram — [NEW]
- Explainer: what we read (your reels, captions, basic profile), what we
  never do (post without your confirmation), button "Continue with
  Instagram" → Meta's own login/consent page (external) → back.
- Result states: connected (@handle, avatar, N reels found) / not a
  Business-Creator account (how to switch) / permission denied / error.
- Then: choose how many recent reels to analyse (default 50) → start profile
  building.

### 6.6 Upload videos — [EXISTING] (`ExperiencedCreatorScreen.jsx`)
Form: social handle, primary niche (Tech, Finance, Fitness, Beauty, Gaming,
Education, Personal Growth), drag-and-drop zone ("MP4, MOV, AVI — up to 10
videos"), file list with remove, button "Analyse My Videos".

### 6.7 New creator — [EXISTING] (`NewCreatorScreen.jsx`)
Form: name, handle, niche, "Content preferences & ideas (optional)",
button "Create My Profile". Note in design: style scores will show `—` until
the creator has real videos.

### 6.8 Profile building (progress) — [EXISTING, CHANGED]
Today (inside the upload screen): "Processing videos", steps:
1. Uploading videos (→ for Instagram: "Importing reels")
2. Transcribing & extracting text style (Module 1)
3. Building creator knowledge base
4. Visual & audio analysis (Module 2)
5. Generating creator profile

"Takes a few minutes per video — keep this tab open." → **change to** "You
can leave this page; we'll notify you when it's ready" (runs as a job).
Error state with retry; partial success ("42 of 50 reels analysed, 8 had no
speech").

### 6.9 Profile result — [EXISTING] (done state of upload screen)
"Creator Profile Generated · N videos analysed": handle, niche, dominant hook
(badge), structure (badge), style summary paragraph; button "Go to
Dashboard". **[NEW]:** "Measured style" block (avg shot length + pacing,
speech rate wpm, energy) — already shown on the dashboard, show it here too.

### 6.10 Dashboard — [CHANGED] (`DashboardScreen.jsx`)
Today: "Welcome back, {first name} 👋", "@handle · niche", button **Create
New Video**; stat cards Published / Scheduled / Drafts / Videos Analysed;
creator profile card (niche, dominant hook, structure, style summary,
measured style: avg shot, speech rate, energy); "Recent Content" list (title,
date, niche, views, status badge Published/Scheduled/Draft/Processing/Failed)
with empty state "No content yet". *Content history is mock data today.*
Needed:
- **Plan & usage card [NEW]:** plan name, renewal date, meters for scripts /
  renders / research runs, Upgrade button.
- **Per-video cards [CHANGED]:** thumbnail, title, status, scores (overall,
  style), output type (XML / video), published link + views (from Instagram),
  actions (open, duplicate, delete).
- **Jobs in progress [NEW]:** running renders / profile builds with progress.
- Profile card: "Re-analyse profile" action (e.g. after 20 new reels).

### 6.11 Ideation — choose a path — [EXISTING] (`IdeationScreen.jsx`)
"Ideation — Choose how you want to find your next content topic." Two cards:
**I have my own idea** ("Enter your topic and we'll generate
creator-personalised scripts around it.") and **Find trending ideas**
("Research Agent scans your niche for high-performing topics matched to your
style.").

### 6.12 Own idea + idea report — [CHANGED → NEW report]
Today: textarea ("e.g. Why most developers are learning the wrong things in
2025") → "Continue to Script Generation" (no research at all). Needed:
- Textarea + two buttons: **[Check my idea]** (primary, "uses 1 research
  credit") and "Skip — write scripts directly" (secondary).
- **Progress:** "Searching recent videos on your idea… → Measuring demand →
  Finding what works → Comparing with your niche".
- **Idea report card:**
  ```
  Your idea: "Sahiwal ki kulfi review"
  Demand      ███████░░░  72   good      ⓘ
  Saturation  medium (≈15 videos in 14 days) ⓘ
  Your fit    ████████░░  81   fits you  ⓘ
  Angles working right now:
    • Cheap vs expensive comparison   (3 videos, 4.2× their usual views)
    • The story of the oldest shop
  Evidence: 3 top videos (thumbnail, title, views, channel) → open on YouTube
  Similar trending topics:                       ← hybrid suggestions
    • "Street food under Rs 100"   trend 85 · 78% similar  [Use this instead]
    • "Pakistan's oldest food shops" trend 79 · 64% similar [Use this instead]
  [ Write scripts on my idea → ]
  ```
- States: **low confidence** ("Not enough recent videos to judge this idea —
  you can still continue"), **outside your niche** warning (low fit), no
  similar trends (hide that section), research unavailable (quota/API down:
  "Couldn't check right now — continue without trend data"), out of research
  credits (upgrade modal).
- Later phase: **"Blend"** option — an AI-suggested angle combining the idea
  with a trend ("Sahiwal ki kulfi — under Rs 100?").

### 6.13 Trending ideas — [EXISTING] (`IdeationScreen.jsx`, path B)
Progress card "Research Agent processing…" with steps: Analysing recent
trends → Filtering by niche → Comparing creator relevance → Ranking topics.
Results: "N trending topics found" + Refresh; each **topic card**: title,
Trend score /100, Creator Fit /100, "why this" quote, "View N supporting
signals" expandable list, **Select**. Error state with "Try again".
**[NEW]:** "low confidence" badge on weak topics, evidence videos inside the
expanded card, credit cost on Refresh, "data from YouTube Shorts, last 14
days" footnote.

### 6.14 Topic confirmation — [EXISTING] (`TopicSelectScreen.jsx`)
"Select your topic": selectable topic cards (trend score, creator fit, why
this, 2 signals, ✓ when selected; click again to deselect), "+ Use my own
idea instead" inline input, "Selected topic" banner with Clear, button
**Generate Scripts**. Empty state: "No trending topics loaded." **[CHANGED]:**
show the cost ("Generates 3 variants · uses 1 script credit"). Consider
merging this screen into Ideation (it duplicates the selection step).

### 6.15 Script variants — [EXISTING, CHANGED] (`ScriptScreen.jsx`)
- **Generating:** "Generating script variants…", topic, steps: Retrieving
  creator context → Generating script variants → Evaluating hooks →
  Evaluating structure → Checking creator style consistency → Selecting
  candidates.
- **Results:** "Script Variants — 3 candidates generated for: '{topic}'",
  Regenerate. Each **variant card**: label (VARIANT A/B/C), **overall %**
  badge (green ≥ 70 pass, red below), hook type badge (e.g. Curiosity Gap,
  Bold Claim), structure name, Edit, Select; hook text; score bars **Style
  Consistency, Hook Alignment, Structure Align., Timing Fit**; "Preview N
  scenes" (time, segment, voiceover).
- **[NEW] score explainer:** ⓘ next to "overall" opens a panel: the 4
  metrics, how each is measured, and that overall = simple average (§7). A
  metric that couldn't be measured shows `—` with the reason ("no past
  transcripts yet").
- **[NEW]** "Why this score" feedback list per variant (the evaluator's
  concrete feedback, e.g. "Voiceover is 98 words; 30 s is about 80. Cut ~18
  words.").
- **Edit hook modal:** "Editing the hook. After saving, scores will be
  recalculated." **[CHANGED]:** actually re-score after edit (today it does
  not).
- **Failed:** "No candidates met the quality threshold" with each variant's
  score and an example issue; Regenerate, Change topic, Edit manually.
- **Backend error:** "Script generation failed — Try again".
- Remove the "Demo: show failure state" link.

### 6.16 Production plan — [EXISTING] (`ProductionScreen.jsx`)
"Production Plan — N scenes · Total: 0:30". Per scene card: segment badge,
time range, Voiceover, Caption, Shot Description, Visual / B-Roll, Edit.
Edit modal: start/end time, voiceover, caption overlay, shot description,
visual suggestion. Primary: Continue to output. **[NEW]:** live total
duration and word-count vs budget warning while editing.

### 6.17 Output choice — [EXISTING] (`OutputChoiceScreen.jsx`)
"How do you want to output your video?" Two cards: **Export Editable XML**
(Premiere Pro project with clips, captions, audio tracks, timestamps) and
**Generate AI Video** (badge "Prototype"). **[CHANGED]:** show credit cost on
the video card ("1 render credit"); Free plan → video card shows lock +
Upgrade.

### 6.18 XML export — [EXISTING] (`XmlExportScreen.jsx`)
"Production Plan Ready" summary → Export → progress (Preparing timeline →
Mapping clips → Building tracks → Adding timestamps → Adding captions →
Generating XML) → "XML Project Ready · All tracks generated" checklist →
Download, Continue to Publish.

### 6.19 Creator photos step — [EXISTING] (`CreatorPhotosStep.jsx`)
"Your Photos — Optional: upload your own photos (campus, products, events).
Each scene gets the best-fitting photo; you confirm or swap it before the
video is rendered." Drop zone ("JPG, PNG, WEBP — up to 40 photos"), progress
("Uploading photos…", "Matching photos to scenes…"), per-scene suggestion
with alternatives to swap (and "no good match → stock/generated"), buttons
"Skip — no photos" / "Generate without my photos" / Generate. Info alert in
Generic mode. **[NEW]:** saved photo library reused across videos (manage in
Settings).

### 6.20 AI video — render + preview — [EXISTING, CHANGED] (`VideoGenScreen.jsx`)
- Mode toggle: **Personalised** vs **Generic baseline**.
- **Generating:** "Generating AI Video…" steps (voiceover → shots → assets →
  render) "Takes a few minutes on the GPU". **[CHANGED]:** queued state
  ("Position 2 in queue"), leave-and-notify, cancel.
- **Preview:** "AI Video Preview — click any scene to inspect and edit":
  video player, timeline of scenes, selected-scene panel (voiceover, shots,
  asset source label: your photo / stock / generated / placeholder), Edit
  Scene modal (times, subtitle/voiceover, caption overlay), Choose Visual
  Asset modal, buttons Your photos / Regenerate / Continue to Publish.
- **Measured style fidelity** panel: Style fidelity, Visual look match, Cut
  pacing match, Speech rate match, CLIP alignment (each with ⓘ).
- **[NEW]:** "Regenerate uses 1 render credit" confirmation; download MP4.

### 6.21 Publish — [CHANGED] (`PublishScreen.jsx`, mock today)
Today: video summary, Caption field, **Publish Now** / **Schedule Post**
(date + time), states Publishing… / Scheduling… / Published! / Scheduled
Successfully. Needed:
- Connected account header (@handle, avatar) or "Connect Instagram" if not
  connected.
- AI caption suggestion + hashtags (editable), cover frame picker.
- Publish now (confirm dialog) / Schedule (date, time, timezone).
- Real states: uploading to Instagram, processing on Instagram, published
  (link "View on Instagram"), failed (reason + retry), token expired
  (reconnect).
- Free/Creator plan: schedule locked → Upgrade.

### 6.22 Library: My content & Scheduled — [NEW]
- **My content:** grid/list of all videos and drafts with filters (status,
  output type, date), search, open/duplicate/delete.
- **Scheduled:** calendar + list of scheduled posts, reschedule, cancel.

### 6.23 Settings — [NEW]
Tabs:
- **Account:** name, email, password change, delete account (with export of
  my data).
- **Connected accounts:** Instagram (connected @handle, permissions,
  reconnect, disconnect).
- **Creator profile:** niche, measured style, re-analyse, which reels are in
  the knowledge base, photo library.
- **Billing & plan:** see 6.24.
- **Notifications:** email when a render/profile job finishes.

### 6.24 Billing & plan — [NEW]
Current plan + renewal date, usage meters (scripts, renders, research runs)
with reset date, usage history table (date, action, credits), invoices/
receipts, **Change plan**, **Cancel subscription** (confirm; stays active
until period end), payment method (managed on the provider's page).

### 6.25 Checkout & payment result — [NEW]
"Upgrade to Creator" summary → **redirect to the payment provider's hosted
checkout** (external page, sandbox in development) → back to **Payment
successful** (new plan, new limits, "Continue where you left off") or
**Payment failed / cancelled** (retry, choose another plan). A "pending
confirmation" state while the provider's webhook arrives.

### 6.26 Out-of-credits modal / paywall — [NEW]
Triggered before a costly action when the credit is 0: what ran out, when it
resets, plan comparison mini-table, Upgrade (primary), "Not now".

### 6.27 Job tray & notifications — [NEW]
Header icon with a badge; dropdown list of jobs (profile build, research,
scripts, render, publish) with progress, finished ✓ (click to open), failed ✕
(retry). Toasts on completion.

### 6.28 System states (all screens)
Loading skeletons; empty states with one CTA; backend unreachable ("We can't
reach ViralHook right now"); session expired → login; 404.

---

## 7. Score explainer texts (for ⓘ popovers)

| Score | Where | Text |
|---|---|---|
| Style Consistency | Script | How close the script's sentence length, use of "you" and share of questions are to your own past videos. `—` if we have no transcripts of yours yet. |
| Hook Alignment | Script | An AI judge answers 6 fixed questions about the opening line (does it make you keep watching, is it specific, concrete, promises a benefit, matches the hook type, sayable in ~3 s). The judge is checked first against a deliberately weak hook; if it can't tell weak from strong, this score is not shown. |
| Structure Align. | Script | Share of structure checks passed: 5 scenes in order, ends at ~0:30, a real hook, short captions, no repeated scenes, no sentences copied from your past videos. |
| Timing Fit | Script | Spoken words vs what fits 30 s at your speaking speed: full marks within ±15 %. |
| Overall | Script | The average of the scores above that could be measured. 70 % or more passes. |
| Trend score | Research | How strongly recent videos on this topic beat their channels' usual views, how many different channels are posting it, and how well it fits your niche. Based on YouTube Shorts from the last 14 days. |
| Creator Fit | Research | How close the topic is to the topics you usually make videos about. |
| Demand / Saturation | Idea report | Demand: how well recent videos on your idea performed compared with their channel size. Saturation: how many videos on it appeared in the last 14 days. |
| Style fidelity, Visual look, Cut pacing, Speech rate | Video | How closely the rendered video matches your measured visual look, average shot length and speaking speed. |
| CLIP alignment | Video | How well each scene's picture matches what the voiceover describes. |

> Note for the team: the weights behind Overall and Trend score are being
> validated in experiment E2 (human ratings). If they change, update these
> texts.

## 8. Data the UI needs per screen (for implementation)

| Screen | API today | Status |
|---|---|---|
| Auth | `loginUser`, `signupUser` | mock → real auth API |
| Upload / profile build | `processCreatorVideos` → `/onboarding/upload`, `/onboarding/status/{id}` | real |
| New creator | `createNewCreatorProfile` | mock |
| Dashboard history | `getContentHistory` | mock → per-user content API |
| Trending ideas | `fetchTrendingTopics` → `/research/trends` | real |
| Idea report | — | new endpoint (research idea mode) |
| Scripts | `generateScripts` → `/script/generate` | real |
| Production plan | `buildProductionPlan` | client-side mapping |
| XML export | `exportXML` → `/export/xml` | real |
| Creator photos | `uploadCreatorPhotos`, `matchCreatorPhotos` → `/assets/*` | real |
| AI video | `generateAIVideo` → `/video/generate`, `/video/status/{id}` | real (needs GPU) |
| Swap visual | `regenerateVisual` | mock |
| Publish | `getInstagramAccount`, `publishNow`, `schedulePost`, `generateCaption` | mock → Instagram Graph API |
| Billing, usage, settings, library, jobs | — | new |

Unused legacy components to delete during the redesign:
`components/LandingPhase.jsx`, `UploadPhase.jsx`, `ProfilePhase.jsx`,
`IdeationPhase.jsx`, `ExportPhase.jsx`, `Sidebar.jsx`, `phases.js`.

## 9. What to ask the designer for

1. Design system: colours (light + dark), type scale, spacing, components
   (buttons, inputs, cards, badges, score bar/pill, progress steps, modal,
   toast, job tray, credit meter, plan card).
2. Every screen in §6 at desktop (1440 px) and mobile (390 px), including
   its loading, empty, error and out-of-credits states.
3. The full flow §5 as a clickable prototype.
4. Marketing pages: Landing, Pricing.
