import { createContext, useContext, useState, useCallback } from 'react'

const AppContext = createContext(null)

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

export function AppProvider({ children }) {
  // Auth
  const [user, setUser] = useState(null)

  // Onboarding
  const [creatorProfile, setCreatorProfile] = useState(null)

  // Workflow state
  const [selectedTopic, setSelectedTopic]     = useState(null)
  const [trendingTopics, setTrendingTopics]   = useState([])    // real topics from research agent
  const [selectedVariant, setSelectedVariant] = useState(null)
  const [productionPlan, setProductionPlan]   = useState(DEMO === 'photos' ? DEMO_PHOTOS_PLAN : null)
  const [exportXML, setExportXML]             = useState(null)
  const [videoTimeline, setVideoTimeline]     = useState(null)
  const [videoResult, setVideoResult]         = useState(null)    // { videoUrl, evaluation, mode }
  const [publishStatus, setPublishStatus]     = useState(null)

  // Navigation
  const [screen, setScreen] = useState(DEMO === 'photos' ? 'video-gen' : 'auth')
  const navigate = useCallback((s) => setScreen(s), [])

  const logout = useCallback(() => {
    setUser(null)
    setCreatorProfile(null)
    setSelectedTopic(null)
    setTrendingTopics([])
    setSelectedVariant(null)
    setProductionPlan(null)
    setExportXML(null)
    setVideoTimeline(null)
    setVideoResult(null)
    setPublishStatus(null)
    setScreen('auth')
  }, [])

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
        logout,
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
