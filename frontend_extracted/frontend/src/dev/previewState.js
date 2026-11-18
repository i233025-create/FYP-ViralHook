// Development only: open any screen directly with realistic mock data, for
// design review and screenshots — e.g. http://localhost:5173/?preview=production
// Vite removes this from production builds (import.meta.env.DEV is false there).
import {
  MOCK_EXPERIENCED_CREATOR_PROFILE, MOCK_TRENDING_TOPICS, MOCK_SCRIPT_VARIANTS, MOCK_VIDEO_TIMELINE,
} from '../data/mockData'

export const PREVIEW_SCREEN = import.meta.env.DEV
  ? new URLSearchParams(window.location.search).get('preview')
  : null

export function previewState() {
  if (!PREVIEW_SCREEN) return null
  const user = { id: 'u_preview', name: 'Hamza Bhatti', email: 'hamza@example.com', emailVerified: true }
  const profile = { ...MOCK_EXPERIENCED_CREATOR_PROFILE('@hamzaeats', 'Food reviews'), name: 'Hamza Bhatti' }
  const topic = MOCK_TRENDING_TOPICS[0]
  const variants = MOCK_SCRIPT_VARIANTS(topic.topic)
  const variant = variants[0]
  const scenes = variant.scenes || []
  const plan = { id: 'pp_preview', title: topic.topic, totalDuration: scenes[scenes.length - 1]?.endTime || '00:30', scenes }
  const later = ['production', 'output', 'xml-export', 'video-gen', 'publish'].includes(PREVIEW_SCREEN)
  return {
    screen: PREVIEW_SCREEN,
    user: PREVIEW_SCREEN === 'unverified' ? { ...user, emailVerified: false } : user,
    creatorProfile: ['creator-type', 'onboarding-new', 'onboarding-experienced', 'style-ready'].includes(PREVIEW_SCREEN) ? null : profile,
    selectedTopic: PREVIEW_SCREEN === 'ideation' || PREVIEW_SCREEN === 'dashboard' ? null : topic,
    trendingTopics: MOCK_TRENDING_TOPICS,
    selectedVariant: later ? variant : null,
    productionPlan: later ? plan : null,
    videoTimeline: PREVIEW_SCREEN === 'video-done' ? MOCK_VIDEO_TIMELINE(scenes) : null,
  }
}

/** ?preview=style-ready: the "Your style" result shown after uploading videos. */
export function stylePreviewProfile() {
  if (PREVIEW_SCREEN !== 'style-ready') return null
  const p = { ...MOCK_EXPERIENCED_CREATOR_PROFILE('@hamzaeats', 'Food reviews'), name: 'Hamza Bhatti', analyzedVideos: 8 }
  p.rawProfile = {
    ...p.rawProfile,
    audio_analysis: { mean_speech_rate_wpm: 168, energy_label: 'High' },
    visual_analysis: { mean_avg_shot_duration: 1.8, visual_pacing: 'Fast' },
  }
  return p
}
