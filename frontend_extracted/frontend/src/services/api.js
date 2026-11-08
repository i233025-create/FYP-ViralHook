// ─────────────────────────────────────────────────────────────────────────────
// VIRALHOOK — API SERVICE LAYER
//
// Real backend (FastAPI, uvicorn server:app --port 8000) is the default for
// accounts, onboarding profile, research, scripting, XML export and AI video.
// New-creator onboarding and publishing stay mocked (no backend yet).
//
// The UI calls the API at /api on its own origin (Vite dev proxy, nginx in
// Docker), so session cookies are first-party. Sessions are httpOnly cookies:
// this file never sees a token. A 401 triggers one silent /auth/refresh and a
// retry; if that fails, the app returns to the sign-in screen.
//
// Override in frontend/.env.local:
//   VITE_USE_REAL_BACKEND=false        → whole UI on mock data (offline demo)
//   VITE_API_TARGET=http://host:8000   → where the dev proxy sends /api
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
const PROFILE_POLL_MS = 2000

// ── Backend switch ─────────────────────────────────────────────────────────
export const USE_REAL_BACKEND = import.meta.env.VITE_USE_REAL_BACKEND !== 'false'
export const API_BASE = import.meta.env.VITE_API_BASE || '/api'

/** An API failure with the HTTP status (0 = server unreachable). */
export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

// FastAPI sends `detail` as a string, or as a list of field errors (422).
function detailMessage(detail) {
  if (!detail) return ''
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((d) => {
      const field = d.loc?.[d.loc.length - 1]
      if (field === 'email') return 'Please enter a valid email address.'
      return field ? `${field}: ${d.msg}` : d.msg
    }).join(' ')
  }
  return String(detail)
}

// The app shell registers what to do when a session can't be renewed.
let onSessionExpired = () => {}
export function setSessionExpiredHandler(fn) { onSessionExpired = fn }

// Several requests may get a 401 at once; they share one refresh call.
let refreshing = null
function refreshSession() {
  refreshing ||= fetch(`${API_BASE}/auth/refresh`, { method: 'POST', credentials: 'include' })
    .then((r) => r.ok)
    .catch(() => false)
    .finally(() => { refreshing = null })
  return refreshing
}

/**
 * The one way to call the backend. Sends the session cookies, renews an
 * expired session once and retries, and turns errors into ApiError with a
 * readable message.
 */
async function request(path, { method = 'GET', json, form, retry = true } = {}) {
  const init = { method, credentials: 'include', headers: {} }
  if (json !== undefined) {
    init.headers['Content-Type'] = 'application/json'
    init.body = JSON.stringify(json)
  }
  if (form) init.body = form

  let res
  try {
    res = await fetch(`${API_BASE}${path}`, init)
  } catch {
    throw new ApiError("Can't reach the ViralHook server. Check that the backend is running.", 0)
  }
  if (res.status === 401 && retry && !path.startsWith('/auth/')) {
    if (await refreshSession()) return request(path, { method, json, form, retry: false })
    onSessionExpired()
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new ApiError(detailMessage(err.detail) || `Server error ${res.status}`, res.status)
  }
  return res.status === 204 ? null : res.json()
}

const apiFetch = (path, body) => request(path, { method: 'POST', json: body })

// ── Auth ──────────────────────────────────────────────────────────────────────

/** POST /auth/login → { user } */
export async function loginUser({ email, password }) {
  if (!USE_REAL_BACKEND) {
    await delay(600)
    const user = MOCK_USERS.find((u) => u.email === email && u.password === password)
    if (!user) throw new ApiError('Wrong email or password.', 401)
    const { password: _, ...safe } = user
    return { user: { ...safe, emailVerified: true } }
  }
  return request('/auth/login', { method: 'POST', json: { email, password } })
}

/** POST /auth/signup → { user } (signed in; a verification email is sent) */
export async function signupUser({ name, email, password }) {
  if (!USE_REAL_BACKEND) {
    await delay(600)
    return { user: { id: 'u_' + Date.now(), name, email, emailVerified: true } }
  }
  return request('/auth/signup', { method: 'POST', json: { name, email, password } })
}

/** POST /auth/logout — ends this device's session (best effort). */
export async function logoutUser() {
  if (!USE_REAL_BACKEND) return
  await request('/auth/logout', { method: 'POST' }).catch(() => {})
}

/**
 * The signed-in user, or null. Renews an expired access cookie once, so a
 * returning visitor with a valid refresh cookie stays signed in.
 */
export async function getCurrentUser() {
  if (!USE_REAL_BACKEND) return null
  try {
    return (await request('/auth/me')).user
  } catch (err) {
    if (err.status !== 401) throw err
  }
  if (!(await refreshSession())) return null
  try {
    return (await request('/auth/me')).user
  } catch (err) {
    if (err.status === 401) return null
    throw err
  }
}

export const verifyEmail = (token) => request('/auth/verify-email', { method: 'POST', json: { token } })
export const resendVerification = () => request('/auth/resend-verification', { method: 'POST' })
export const requestPasswordReset = (email) => request('/auth/forgot-password', { method: 'POST', json: { email } })
export const resetPassword = (token, password) =>
  request('/auth/reset-password', { method: 'POST', json: { token, password } })

/** GET /onboarding/profile → the signed-in user's creator profile, or null if none yet. */
export async function getCreatorProfile() {
  if (!USE_REAL_BACKEND) return null
  try {
    return (await request('/onboarding/profile')).profile
  } catch (err) {
    if (err.status === 404) return null
    throw err
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
 * POST /onboarding/upload (videos + handle + niche) → poll GET /onboarding/status/{jobId}
 * → GET /onboarding/profile. The backend saves the videos as the new creator,
 * runs Module 1 (text RAG) + Module 2 (multimodal) and builds the REAL profile.
 * onStep({ id, label, detail }) fires on every progress change.
 */
export async function processCreatorVideos({ files = [], handle, niche, onStep }) {
  if (USE_REAL_BACKEND) {
    const form = new FormData()
    files.forEach((f) => form.append('files', f, f.name))
    form.append('handle', handle || '')
    form.append('niche', niche || '')

    const { jobId } = await request('/onboarding/upload', { method: 'POST', form })

    for (;;) {
      await delay(PROFILE_POLL_MS)
      const job = await request(`/onboarding/status/${jobId}`)
      if (onStep) onStep({ id: job.step, label: job.stepLabel, detail: job.detail })
      if (job.status === 'error') throw new Error(job.error || 'Profile extraction failed')
      if (job.status === 'done') break
    }

    const params = new URLSearchParams({ handle: handle || '', niche: niche || '' })
    return { profile: (await request(`/onboarding/profile?${params}`)).profile }
  }

  const steps = [
    { id: 1, label: 'Uploading videos', duration: 1200 },
    { id: 2, label: 'Transcribing & extracting text style (Module 1)', duration: 1500 },
    { id: 3, label: 'Building creator knowledge base', duration: 1800 },
    { id: 4, label: 'Visual & audio analysis (Module 2)', duration: 2000 },
    { id: 5, label: 'Generating creator profile', duration: 1200 },
  ]
  for (const step of steps) {
    await delay(step.duration)
    onStep(step)
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
export async function generateAIVideo({ plan, mode = 'personalised', assetLibraryId = null, sceneAssets = null, onStep }) {
  if (USE_REAL_BACKEND) {
    const { jobId } = await apiFetch('/video/generate', { plan, mode, assetLibraryId, sceneAssets })
    for (;;) {
      await delay(VIDEO_POLL_MS)
      const job = await request(`/video/status/${jobId}`)
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

// ── Creator photos (experiment E3: SigLIP match → creator review) ─────────────

/** Backend photo URLs are relative; blob: URLs (mock mode) are used as-is. */
export const photoUrl = (url) => (!url || url.startsWith('blob:') ? url : `${API_BASE}${url}`)

/**
 * POST /assets/upload (multipart files[]) → { libraryId, photos: [{ name, url }] }
 */
export async function uploadCreatorPhotos(files) {
  if (USE_REAL_BACKEND) {
    const form = new FormData()
    files.forEach((f) => form.append('files', f, f.name))
    return request('/assets/upload', { method: 'POST', form })
  }
  await delay(500)
  return { libraryId: 'mock', photos: files.map((f) => ({ name: f.name, url: URL.createObjectURL(f) })) }
}

/**
 * POST /assets/match { libraryId, plan }
 * → { threshold, photos, scenes: [{ index, segment, clipIdea, ranked: [{ name, score }], suggested }] }
 * `suggested` is the best photo above the threshold (null → stock / generated);
 * the creator confirms or swaps it before rendering.
 */
export async function matchCreatorPhotos({ libraryId, plan, photos = [] }) {
  if (USE_REAL_BACKEND) return apiFetch('/assets/match', { libraryId, plan })
  await delay(600)
  return {
    threshold: 0.064,
    photos,
    scenes: (plan?.scenes || []).map((sc, index) => ({
      index, segment: sc.segment, clipIdea: sc.visual || sc.clip_idea || '',
      ranked: photos.map((p) => ({ name: p.name, score: null })), suggested: null,
    })),
  }
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
