import { createContext, useContext, useState, useCallback } from 'react'

const AppContext = createContext(null)

export function AppProvider({ children }) {
  // Auth
  const [user, setUser] = useState(null)

  // Onboarding
  const [creatorProfile, setCreatorProfile] = useState(null)

  // Workflow state
  const [selectedTopic, setSelectedTopic]     = useState(null)
  const [trendingTopics, setTrendingTopics]   = useState([])    // real topics from research agent
  const [selectedVariant, setSelectedVariant] = useState(null)
  const [productionPlan, setProductionPlan]   = useState(null)
  const [exportXML, setExportXML]             = useState(null)
  const [videoTimeline, setVideoTimeline]     = useState(null)
  const [videoResult, setVideoResult]         = useState(null)    // { videoUrl, evaluation, mode }
  const [publishStatus, setPublishStatus]     = useState(null)

  // Navigation
  const [screen, setScreen] = useState('auth')
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
