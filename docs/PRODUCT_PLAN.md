# ViralHook — Product Plan

> Agreed 2026-11-08. Goal set by the supervisor: **ViralHook is built as a
> real product with subscription plans.** Every piece of work is judged
> against that goal: multi-user, metered, production-shaped, honest numbers.
> **Quality over deadline:** phases end when their "done when" checklist is
> met, not on a date.

---

## 1. Decisions taken

| # | Topic | Decision |
|---|---|---|
| D1 | Priority | Quality first; the evaluation date is not a planning constraint. |
| D2 | Instagram | Official **Instagram Graph API (Instagram Login)** for Business/Creator accounts. **Both** import (onboarding: reels + captions → profile/RAG) **and** publish (+ scheduling). Import first. Test-user (development) mode for the FYP; architecture ready for Meta App Review later. |
| D3 | Billing | Our own **plans / entitlements / usage metering** layer, enforced in the backend, **plus** a real payment provider in **sandbox** mode (pricing → checkout → webhook → plan change → cancel). Provider-agnostic adapter. Stripe is not available for Pakistani merchants; candidates Safepay, PayFast PK, Paddle, Lemon Squeezy — verify current subscription and payout support from their docs before choosing. |
| D4 | Own-idea research | "Idea mode" in the Research Agent: queries generated from the idea, then the existing discovery → scoring → clustering → labelling steps. Shows **demand, saturation, creator fit, working angles, evidence**. Runs on a **[Check my idea]** click (1 research credit). Never blocks the creator; "low confidence" when data is thin. |
| D5 | Hybrid suggestions | On: up to 2–3 trending topics closest to the idea (embedding similarity above a threshold tuned on real data; none shown if none are close). The "blend" option (LLM-merged angle) comes after options 1–2 are solid. |
| D6 | Score formula | Keep the measured, explainable formula; document the basis of every component and **validate it against human ratings in E2**; reweight or drop components that don't correlate. |
| D7 | Roles | See §3. |

## 2. Workstreams

### W1 — Auth & per-user workspace (foundation)
Today auth is a frontend mock (`services/api.js`) and the backend is
single-tenant (one global creator profile, `chroma_db`, Qdrant snapshot,
in-memory jobs).
- Users table (SQLite now, Postgres-ready), argon2 password hashing, JWT in
  an httpOnly cookie, refresh/expiry, password reset, rate-limited login.
- **Per-user workspace:** profile, transcripts, vector collections, creator
  photos, outputs and jobs stored per user; every endpoint scoped to the
  logged-in user; no cross-user access (tests for this).
- Migrate today's single creator into a user account.
- Later: Google sign-in.

### W2 — Instagram integration
- Meta developer app, Instagram Login OAuth, encrypted token storage, token
  refresh, disconnect.
- **Import:** list the creator's reels + captions → download → existing
  Module 1/2 pipeline → profile + knowledge base. Replaces manual upload as
  the main onboarding path (upload stays as fallback).
- **Publish:** container create → status poll → publish; needs the video at
  a public URL (storage from W7). Then **scheduling** (scheduled-jobs table +
  worker).
- Privacy policy + terms pages (required by Meta).

### W3 — UI redesign
- `docs/UI_WORKFLOW.md` → design on claude.ai (design system, all screens and
  states, desktop + mobile) → implement on real APIs.
- Rename `frontend_extracted/frontend/` → `frontend/`, delete legacy
  components, replace every remaining mock with a real endpoint.

### W4 — Research idea mode + hybrid suggestions
- `run_research(..., idea=...)`: idea → 2–3 queries → shared steps 2–6;
  add a **saturation** measure (recent video count on the idea) and
  **working angles** (labels of the best-performing clusters).
- Hybrid: embed the idea, compare with the niche's trending clusters (6-hour
  cache reused; one research credit covers both).
- New endpoint + frontend idea report; scripting receives the same `trend`
  context shape for both paths.
- Report limitation: YouTube Shorts as a proxy for Instagram (no public
  Instagram trend API).

### W5 — Score justification & E2 validation
- Write the basis of every component (stylometry; platform timing
  constraint; rule-based structure checks; LLM-as-a-judge with rubric and
  control calibration; equal weights as the default without evidence —
  Dawes 1979) and of the research weights.
- **E2:** generate scripts across modes (no history / retrieval / full
  pipeline), collect blind human ratings (team + outside raters), report
  Spearman correlation per component and overall; reweight or drop weak
  components; optional 5th style metric (e5 embedding similarity to the
  creator's transcripts).
- Update the ⓘ texts in the UI if weights change.

### W6 — Subscriptions & billing
- Plans and entitlements config (Free / Creator / Pro; limits per §6.2 of
  the UI doc), `usage` ledger written by every metered job, backend check
  before a job starts, monthly reset.
- Payment adapter + chosen provider in sandbox: checkout session, webhook
  (verified signatures, idempotent), plan change, cancel at period end,
  failed payment handling.
- Pricing in PKR + USD, derived from measured cost per render (GPU time) and
  per script (LLM time).

### W7 — GPU worker, job queue & storage
- Persistent job queue (replaces in-memory jobs): profile build, research,
  scripts, render, publish; status API for the UI job tray.
- GPU worker on the lab PC pulling render jobs; CPU work stays on the API
  server.
- Object storage for videos/photos with public (signed) URLs — needed for
  Instagram publishing and downloads.
- Measure cost per render and per script (input for pricing).

### W8 — Research experiments (finish)
- **E1 v2:** 150 reels (3 creators × 50) downloaded; transcription running;
  topic labelling by the team; run caption and topic conditions on the top
  methods (multi-e5-small, bge-m3, BM25, hybrid, MiniLM); update REPORT.md.
- E3 is done and integrated; extend only if E1/E2 reveal a need.

### W0 — Consolidation (before new features)
Still open from the 2026-10-27 plan: the unmerged branch chain
(main → feat/research-agent-v2 → feature/video-generation →
feature/rag-experiments) goes into `dev` via PRs; delete stale branches
(evaluation-framework, instagram-integration, multimodal-rag, ci-cd-pipeline,
poc); clean the repo root (zip, test scripts, transcript dumps, PDF); CI
green. New work branches from `dev`.

## 3. Owners

| Person | Workstreams |
|---|---|
| **Zeenab** | W4 research idea mode + hybrid · W5 score justification + E2 |
| **Hashaam** | W7 GPU worker, job queue, storage · W2 Instagram import + publish |
| **Rabeeha** | W0 consolidation · W1 auth + per-user workspace · W6 billing · W3 UI (brief → design → implementation) · W8 E1 v2 |
| **Everyone** | E1 v2 topic labelling (~50 reels each) · E2 human ratings |

Rabeeha's load is the heaviest; if needed, screens in W3 are split once the
others' workstreams are done.

## 4. Order and dependencies

```
W0 consolidation
   │
   ▼
W1 auth + per-user workspace ──────────────┬──► W6 billing (needs users + jobs)
   │                                       ├──► W2 Instagram (tokens per user)
   │                                       └──► W3 implementation (real APIs)
   │
   │  in parallel, not blocked by W1:
   ├── W4 idea mode (Zeenab)        ─► plugs into per-user profile when W1 lands
   ├── W5 E2 design + generation    ─► human ratings
   ├── W7 job queue + GPU worker + storage (Hashaam) ─► W2 publish, W6 metering
   ├── W3 design on claude.ai (from UI_WORKFLOW.md)
   └── W8 E1 v2 labelling + run
```

### Phases (each ends on its checklist, not a date)

**Phase 1 — Foundation**
- W0 merged and CI green.
- W1: users can sign up/log in; two test users have fully separate data
  (automated test); the old single creator migrated.
- W7: jobs survive a server restart; a render runs on the lab-PC GPU worker
  from the queue.
- W3: design system + core screens designed.
- W8: E1 v2 transcribed and labelled.

**Phase 2 — Product core**
- W4: idea report and hybrid suggestions working end-to-end for own ideas.
- W2: Connect Instagram → reels imported → profile built (test users).
- W3: core flow implemented on real APIs (no mocks left in that flow).
- W5: E2 scripts generated; human rating sheet out.
- W8: E1 v2 results in the report.

**Phase 3 — Business layer**
- W6: plans, metering and sandbox checkout end-to-end (upgrade, renew,
  cancel, failed payment); every metered action checks credits.
- W2: publish + schedule to Instagram from the app.
- W5: E2 correlations reported; weights confirmed or changed; UI texts
  updated.
- W3: remaining screens (library, settings, billing, landing, pricing).

**Phase 4 — Hardening**
- Security pass (auth, tokens, webhooks, uploads), error states on every
  screen, logging, backups.
- Full end-to-end demo on the lab PC + a recorded backup demo video.
- Final report and documentation.

## 5. Laptop vs GPU

| 💻 Laptops (CPU) | 🖥️ Lab PC (GPU) |
|---|---|
| W0, W1, W2, W3, W6 (all web/backend work) | SDXL Lightning image generation (requires CUDA) |
| W4 research (YouTube API, MiniLM, small LLM for labels) | Fast LLM for scripting and the hook judge (Ollama `qwen2.5:3b`; CPU works but is slow) |
| W5 writing, E2 analysis | E2 bulk script generation |
| W8 E1 v2 (retrieval models are CPU-friendly; Whisper `small` ≈ 20–40 s/reel) | Video render jobs (W7 worker), end-to-end tests |
| Tests, CI | Bulk Whisper if laptop transcription is too slow |

## 6. Risks

| Risk | Mitigation |
|---|---|
| Meta app setup/App Review delays | Test-user mode is enough for the FYP; keep upload as fallback onboarding. |
| No payment provider supports PK subscriptions in sandbox | Verify first; the billing layer is provider-agnostic, so the provider can change. |
| Lab PC availability | Job queue lets renders wait; CPU fallback for LLM (slow) keeps non-video flows working. |
| E2 shows the score formula correlates poorly with humans | That is a finding, not a failure: reweight using the ratings and report it. |
| Instagram API changes / rate limits | Official API only in the product; cache imports; respect rate limits. |
| Rabeeha's workload | Split W3 screens when others free up. |

## 7. Open questions
- Exact plan prices (after W7 cost measurement).
- Payment provider (after the docs check in W6).
- Hybrid "blend" option: in scope after Phase 2 if time allows.
- Who the outside raters for E2 are, and how many.
