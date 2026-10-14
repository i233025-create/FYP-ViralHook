// ─────────────────────────────────────────────────────────────────────────────
// VIRALHOOK — API SERVICE LAYER
//
// Real backend (FastAPI, uvicorn server:app --port 8000) is the default for
// onboarding profile, research, scripting, XML export and AI video.
// Auth, new-creator onboarding and publishing stay mocked (no backend yet).
//
// Override in frontend/.env.local:
//   VITE_USE_REAL_BACKEND=false        → whole UI on mock data (offline demo)
//   VITE_API_BASE=http://host:8000     → backend on another machine
// ─────────────────────────────────────────────────────────────────────────────

import {
  MOCK_USERS,
  MOCK_NEW_CREATOR_PROFILE,
  MOCK_EXPERIENCED_CREATOR_PROFILE,
  MOCK_TRENDING_TOPICS,
  MOCK_SCRIPT_VARIANTS,
  MOCK_FAILED_VARIANTS,
  MOCK_PRODUCTION_PLAN,
  generateMockXML,
  MOCK_VIDEO_TIMELINE,
  MOCK_INSTAGRAM_ACCOUNT,
  MOCK_CAPTION,
  MOCK_CONTENT_HISTORY,
} from '../data/mockData'

const delay = (ms) => new Promise((r) => setTimeout(r, ms))

// ── Backend switch ─────────────────────────────────────────────────────────
export const USE_REAL_BACKEND = import.meta.env.VITE_USE_REAL_BACKEND !== 'false'
export const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

async function apiFetch(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `Server error ${res.status}`)
  }
  return res.json()
}

// ── Auth ──────────────────────────────────────────────────────────────────────

/**
 * POST /auth/login
 * Returns: { user } | throws Error
 */
export async function loginUser({ email, password }) {
  await delay(900)
  const user = MOCK_USERS.find(
    (u) => u.email === email && u.password === password
  )
  if (!user) throw new Error('Invalid email or password.')
  const { password: _, ...safe } = user
  return { user: safe }
}

/**
 * POST /auth/signup
 * Returns: { user }
 */
export async function signupUser({ name, email, password }) {
  await delay(1000)
  // Mock: any signup succeeds
  return {
    user: { id: 'u_' + Date.now(), name, email, handle: '@' + name.toLowerCase().replace(/\s+/g, '') },
  }
}

// ── Creator Onboarding ────────────────────────────────────────────────────────

/**
 * POST /onboarding/new-creator
 * Returns: { profile }
 */
export async function createNewCreatorProfile(formData) {
  await delay(800)
  return { profile: MOCK_NEW_CREATOR_PROFILE(formData) }
}

/**
 * GET /onboarding/profile
 * Video upload/transcription is CLI-based in the PoC (module1 + module2 main.py),
 * so the steps below only pace the UI; the profile itself is the REAL one the
 * backend built from the creator's videos. Throws if the backend has none.
 */
export async function processCreatorVideos({ handle, niche, onStep }) {
  const steps = [
    { id: 1, label: 'Uploading videos', duration: 1200 },
    { id: 2, label: 'Extracting transcripts', duration: 1500 },
    { id: 3, label: 'Building creator knowledge base', duration: 1800 },
    { id: 4, label: 'Analysing creator style patterns', duration: 2000 },
    { id: 5, label: 'Generating creator profile', duration: 1200 },
  ]
  for (const step of steps) {
    await delay(USE_REAL_BACKEND ? 300 : step.duration)
    onStep(step)
  }

  if (USE_REAL_BACKEND) {
    const params = new URLSearchParams({ handle: handle || '', niche: niche || '' })
    let res
    try {
      res = await fetch(`${API_BASE}/onboarding/profile?${params}`)
    } catch (_) {
      throw new Error(`Backend not reachable at ${API_BASE}. Start it with: uvicorn server:app --port 8000`)
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || `Profile request failed (${res.status})`)
    }
    return { profile: (await res.json()).profile }
  }

  return { profile: MOCK_EXPERIENCED_CREATOR_PROFILE(handle, niche) }
}

// ── Research / Trends ─────────────────────────────────────────────────────────

/**
 * POST /research/trends
 * Returns: { topics }
 */
export async function fetchTrendingTopics({ niche, onStep }) {
  const steps = [
    { id: 1, label: 'Analysing recent trends' },
    { id: 2, label: 'Filtering by niche' },
    { id: 3, label: 'Comparing creator relevance' },
    { id: 4, label: 'Ranking topics' },
  ]

  if (USE_REAL_BACKEND) {
    // Emit steps manually while the real call runs (backend is synchronous)
    for (let i = 0; i < steps.length - 1; i++) {
      if (onStep) onStep(steps[i])
      await delay(400)
    }
    const data = await apiFetch('/research/trends', { niche: niche || 'Tech' })
    if (onStep) onStep(steps[steps.length - 1])
    return data  // { topics: [...] }
  }

  for (const step of steps) {
    await delay(900)
    if (onStep) onStep(step)
  }
  return { topics: MOCK_TRENDING_TOPICS }
}

// ── Script Generation ─────────────────────────────────────────────────────────

/**
 * POST /script/generate
 * Returns: { variants } | { failed: true, variants }
 */
export async function generateScripts({ topic, trend = null, creatorProfile, forceFail = false, onStep }) {
  const steps = [
    { id: 1, label: 'Retrieving creator context' },
    { id: 2, label: 'Generating script variants' },
    { id: 3, label: 'Evaluating hooks' },
    { id: 4, label: 'Evaluating structure' },
    { id: 5, label: 'Checking creator style consistency' },
    { id: 6, label: 'Selecting candidates' },
  ]

  if (USE_REAL_BACKEND && !forceFail) {
    for (let i = 0; i < steps.length - 1; i++) {
      if (onStep) onStep(steps[i])
      await delay(400)
    }
    const data = await apiFetch('/script/generate', { topic, trend, niche: creatorProfile?.niche || 'Tech' })
    if (onStep) onStep(steps[steps.length - 1])
    return data  // { failed: false, variants: [...] }
  }

  for (const step of steps) {
    await delay(700)
    if (onStep) onStep(step)
  }
  if (forceFail) {
    return { failed: true, variants: MOCK_FAILED_VARIANTS(topic) }
  }
  return { failed: false, variants: MOCK_SCRIPT_VARIANTS(topic) }
}

// ── Production Plan ───────────────────────────────────────────────────────────

/**
 * POST /production/plan
 * Converts the selected script variant into a production plan.
 * Since script scenes already come from the real backend (when USE_REAL_BACKEND=true),
 * we just repackage them — no extra backend call needed.
 */
export async function buildProductionPlan(scriptVariant) {
  await delay(400)
  const scenes = scriptVariant?.scenes || []
  // Derive total duration from last scene endTime
  const lastEnd = scenes.length > 0 ? scenes[scenes.length - 1].endTime : '00:30'
  return {
    plan: {
      id: 'pp_' + Date.now(),
      title: scriptVariant?.topic || 'ViralHook Production',
      totalDuration: lastEnd,
      scenes,
    }
  }
}

// ── XML Export ────────────────────────────────────────────────────────────────

/**
 * POST /export/xml
 * Returns: { xml: string }
 */
export async function exportXML({ plan, onStep }) {
  const steps = [
    { id: 1, label: 'Preparing timeline' },
    { id: 2, label: 'Mapping clips' },
    { id: 3, label: 'Building tracks' },
    { id: 4, label: 'Adding timestamps' },
    { id: 5, label: 'Adding captions' },
    { id: 6, label: 'Generating XML' },
  ]

  if (USE_REAL_BACKEND) {
    for (let i = 0; i < steps.length - 1; i++) {
      if (onStep) onStep(steps[i])
      await delay(300)
    }
    const data = await apiFetch('/export/xml', { plan })
    if (onStep) onStep(steps[steps.length - 1])
    return data  // { xml: string }
  }

  for (const step of steps) {
    await delay(600)
    if (onStep) onStep(step)
  }
  return { xml: generateMockXML(plan) }
}

// ── AI Video Generation ───────────────────────────────────────────────────────

// Same order as pipeline/agents/video_agent.py STEPS
export const VIDEO_STEPS = [
  { id: 1, label: 'Planning edit style' },
  { id: 2, label: 'Generating voiceover' },
  { id: 3, label: 'Planning shots' },
  { id: 4, label: 'Fetching visual assets' },
  { id: 5, label: 'Building timeline' },
  { id: 6, label: 'Rendering video' },
  { id: 7, label: 'Evaluating video' },
]
const VIDEO_POLL_MS = 1500

/**
 * POST /video/generate → poll GET /video/status/{jobId}
 * onStep({ id, label, detail }) fires on every progress change.
 * Returns: { timeline, videoUrl, evaluation, mode }   (videoUrl null when mocked)
 */
export async function generateAIVideo({ plan, mode = 'personalised', onStep }) {
  if (USE_REAL_BACKEND) {
    const { jobId } = await apiFetch('/video/generate', { plan, mode })
    for (;;) {
      await delay(VIDEO_POLL_MS)
      const res = await fetch(`${API_BASE}/video/status/${jobId}`)
      if (!res.ok) throw new Error(`Video status error ${res.status}`)
      const job = await res.json()
      if (job.step && onStep) onStep({ id: job.step, label: job.stepLabel, detail: job.detail })
      if (job.status === 'error') throw new Error(job.error || 'Video generation failed')
      if (job.status === 'done') {
        return {
          timeline: MOCK_VIDEO_TIMELINE(job.timeline),   // adds thumbnailBg colours
          videoUrl: `${API_BASE}${job.videoUrl}`,
          evaluation: job.evaluation,
          mode: job.mode,
        }
      }
    }
  }

  for (const step of VIDEO_STEPS) {
    await delay(step.id === 6 ? 1500 : 400)
    if (onStep) onStep(step)
  }
  return { timeline: MOCK_VIDEO_TIMELINE(plan?.scenes), videoUrl: null, evaluation: null, mode }
}

/**
 * POST /video/regenerate-visual
 * Simulates swapping a visual asset for a scene
 */
export async function regenerateVisual({ sceneId }) {
  await delay(1400)
  return { success: true, sceneId }
}

// ── Publishing ────────────────────────────────────────────────────────────────

/**
 * GET /publish/account
 */
export async function getInstagramAccount() {
  await delay(400)
  return { account: MOCK_INSTAGRAM_ACCOUNT }
}

/**
 * POST /publish/now
 */
export async function publishNow({ caption }) {
  await delay(1800)
  return { success: true, postId: 'post_' + Date.now() }
}

/**
 * POST /publish/schedule
 */
export async function schedulePost({ caption, date, time }) {
  await delay(1200)
  return { success: true, scheduledAt: `${date} ${time}` }
}

/**
 * GET /content/history
 */
export async function getContentHistory() {
  await delay(500)
  return { history: MOCK_CONTENT_HISTORY }
}

/**
 * GET /captions/generate
 */
export async function generateCaption({ topic }) {
  await delay(600)
  return { caption: MOCK_CAPTION(topic) }
}
