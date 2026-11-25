import { createContext, useContext, useState, useCallback, useEffect } from 'react'
import {
  USE_REAL_BACKEND, getBilling, getCurrentUser, getCreatorProfile, logoutUser, setSessionExpiredHandler,
} from '../services/api'
import { previewState } from '../dev/previewState'

const AppContext = createContext(null)

// Email links land on /verify-email?token=… and /reset-password?token=…
// (there is no router; the path picks the first screen).
const LINK_SCREENS = { '/verify-email': 'verify-email', '/reset-password': 'reset-password', '/checkout/demo': 'checkout-demo' }
const LINK = {
  screen: LINK_SCREENS[window.location.pathname] || null,
  token: new URLSearchParams(window.location.search).get('token') || new URLSearchParams(window.location.search).get('session') || '',
}

// Demo shortcut: http://localhost:5173/?demo=photos opens the creator-photo
// review step (experiment E3) directly, with a FAST admissions script, so it
// can be shown without running login → research → scripting (needs Ollama).
const DEMO = new URLSearchParams(window.location.search).get('demo')
const DEMO_PHOTOS_PLAN = {
  title: 'FAST Admissions Open',
  scenes: [
    { segment: 'HOOK', visual: 'An aerial view of the whole university campus',
      voiceover: 'Admissions are now open at FAST Islamabad.', caption: 'ADMISSIONS OPEN' },
    { segment: 'SETUP', visual: 'A modern computer lab with rows of computers',
      voiceover: 'Learn to build real software in modern labs.', caption: 'MODERN LABS' },
    { segment: 'MAIN POINT', visual: 'A busy cafeteria where students eat and chat',
      voiceover: 'Make friends for life between classes.', caption: 'CAMPUS LIFE' },
    { segment: 'EVIDENCE', visual: 'A convocation ceremony with students in gowns',
      voiceover: 'Graduate ready for the industry.', caption: 'GRADUATE READY' },
    { segment: 'CONCLUSION', visual: 'Students walking through the university main gate',
      voiceover: 'Apply today, your future starts here.', caption: 'APPLY TODAY' },
  ],
}

// Development only: ?preview=<screen> opens a screen with mock data (src/dev/previewState.js)
const PREVIEW = previewState()
const PREVIEW_SCREENS = { 'video-done': 'video-gen', unverified: 'dashboard', 'style-ready': 'onboarding-experienced' }

export function AppProvider({ children }) {
  // Auth
  const [user, setUser] = useState(PREVIEW?.user ?? null)

  // Onboarding
  const [creatorProfile, setCreatorProfile] = useState(PREVIEW?.creatorProfile ?? null)

  // Workflow state
  const [selectedTopic, setSelectedTopic]     = useState(PREVIEW?.selectedTopic ?? null)
  const [trendingTopics, setTrendingTopics]   = useState(PREVIEW?.trendingTopics ?? [])    // real topics from research agent
  const [selectedVariant, setSelectedVariant] = useState(PREVIEW?.selectedVariant ?? null)
  const [productionPlan, setProductionPlan]   = useState(DEMO === 'photos' ? DEMO_PHOTOS_PLAN : PREVIEW?.productionPlan ?? null)
  const [exportXML, setExportXML]             = useState(null)
  const [videoTimeline, setVideoTimeline]     = useState(PREVIEW?.videoTimeline ?? null)
  const [videoResult, setVideoResult]         = useState(null)    // { videoUrl, evaluation, mode }
  const [publishStatus, setPublishStatus]     = useState(null)
  const [billing, setBilling]                 = useState(null)   // GET /billing/me: plan, usage, subscription
  const [checkoutSession, setCheckoutSession] = useState(null)   // demo checkout opened from the pricing page

  // Navigation. 'boot' = checking for an existing session (see effect below).
  const initialScreen = PREVIEW ? (PREVIEW_SCREENS[PREVIEW.screen] || PREVIEW.screen)
    : DEMO === 'photos' ? 'video-gen' : LINK.screen || (USE_REAL_BACKEND ? 'boot' : 'landing')
  const [screen, setScreen] = useState(initialScreen)
  const navigate = useCallback((s) => setScreen(s), [])
  const [authNotice, setAuthNotice] = useState('')     // shown on the sign-in screen
  const linkToken = LINK.token

  /** Re-read plan + usage (after a job, a payment or a cancel). Failures keep the last value. */
  const refreshBilling = useCallback(async () => {
    try { setBilling(await getBilling()) } catch { /* keep the last known value */ }
  }, [])

  /** After sign-in or session restore: dashboard if the user has a profile, else onboarding. */
  const enterApp = useCallback(async (signedInUser) => {
    setUser(signedInUser)
    refreshBilling()
    let profile = null
    try {
      profile = await getCreatorProfile()
    } catch {
      profile = null   // server hiccup: onboarding still works, dashboard loads later
    }
    if (profile) {
      setCreatorProfile(profile)
      setScreen('dashboard')
    } else {
      setScreen('creator-type')
    }
  }, [refreshBilling])

  const clearState = useCallback(() => {
    setUser(null)
    setBilling(null)
    setCreatorProfile(null)
    setSelectedTopic(null)
    setTrendingTopics([])
    setSelectedVariant(null)
    setProductionPlan(null)
    setExportXML(null)
    setVideoTimeline(null)
    setVideoResult(null)
    setPublishStatus(null)
  }, [])

  const logout = useCallback(async () => {
    await logoutUser()
    clearState()
    setAuthNotice('')
    setScreen('landing')
  }, [clearState])

  // A session that can't be renewed (expired, signed out elsewhere) → sign-in screen.
  useEffect(() => {
    setSessionExpiredHandler(() => {
      clearState()
      setAuthNotice('Your session has ended. Please sign in again.')
      setScreen('auth')
    })
  }, [clearState])

  // Returning visitor: restore the session from the cookie instead of asking to sign in.
  // Preview / offline demo: load the (mock) plan so the meters show something
  useEffect(() => { if (PREVIEW || !USE_REAL_BACKEND) refreshBilling() }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (initialScreen !== 'boot') return
    getCurrentUser()
      .then((u) => (u ? enterApp(u) : setScreen('landing')))
      .catch(() => {
        setAuthNotice("Can't reach the ViralHook server right now.")
        setScreen('auth')
      })
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <AppContext.Provider
      value={{
        user, setUser,
        creatorProfile, setCreatorProfile,
        selectedTopic, setSelectedTopic,
        trendingTopics, setTrendingTopics,
        selectedVariant, setSelectedVariant,
        productionPlan, setProductionPlan,
        exportXML, setExportXML,
        videoTimeline, setVideoTimeline,
        videoResult, setVideoResult,
        publishStatus, setPublishStatus,
        screen, navigate,
        logout, enterApp, authNotice, setAuthNotice, linkToken,
        billing, refreshBilling, checkoutSession, setCheckoutSession,
      }}
    >
      {children}
    </AppContext.Provider>
  )
}

export function useApp() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used within AppProvider')
  return ctx
}
