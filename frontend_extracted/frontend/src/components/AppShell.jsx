import { useApp } from '../context/AppContext'
import {
  LayoutDashboard, Lightbulb, FileText, Clapperboard,
  Download, Instagram, LogOut, Zap, ChevronRight, Hash
} from 'lucide-react'

// ── Sidebar nav items ─────────────────────────────────────────────────────────
const NAV_ITEMS = [
  { screen: 'dashboard',  label: 'Dashboard',      icon: LayoutDashboard },
  { screen: 'ideation',   label: 'Ideation',        icon: Lightbulb },
  { screen: 'script',     label: 'Script',          icon: FileText },
  { screen: 'production', label: 'Production Plan', icon: Clapperboard },
  { screen: 'output',     label: 'Export / Video',  icon: Download },
  { screen: 'publish',    label: 'Publish',         icon: Instagram },
]

// ── Header label per screen ───────────────────────────────────────────────────
const SCREEN_META = {
  dashboard:      { label: 'Dashboard' },
  ideation:       { label: 'Ideation' },
  'topic-select': { label: 'Topic Selection' },
  script:         { label: 'Script Generation' },
  production:     { label: 'Production Plan' },
  output:         { label: 'Export / Video' },
  'xml-export':   { label: 'XML Export' },
  'video-gen':    { label: 'AI Video Generation' },
  publish:        { label: 'Publish' },
}

// ── Unlock logic ──────────────────────────────────────────────────────────────
function isUnlocked(s, { creatorProfile, selectedTopic, selectedVariant, productionPlan }) {
  switch (s) {
    case 'dashboard':  return !!creatorProfile
    case 'ideation':   return !!creatorProfile
    case 'script':     return !!selectedTopic
    case 'production': return !!selectedVariant
    case 'output':     return !!productionPlan
    case 'publish':    return !!productionPlan
    default:           return false
  }
}

export default function AppShell({ children }) {
  const {
    screen, navigate, logout,
    creatorProfile, selectedTopic, selectedVariant, productionPlan,
  } = useApp()

  const noShell = ['auth', 'creator-type', 'onboarding-new', 'onboarding-experienced'].includes(screen)
  if (noShell) return <>{children}</>

  const headerLabel = SCREEN_META[screen]?.label || 'ViralHook'

  return (
    <div className="flex h-screen w-screen overflow-hidden">

      {/* ── Sidebar ─────────────────────────────────────────────────────────── */}
      <aside className="flex flex-col w-60 min-w-[240px] bg-discord-sidebar border-r border-discord-faint/20 z-20">

        {/* Brand */}
        <div className="flex items-center gap-3 px-4 py-4 border-b border-discord-faint/20">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-discord-blurple shadow-md">
            <Zap size={16} className="text-white" />
          </div>
          <div>
            <span className="text-discord-white font-bold text-base tracking-tight">ViralHook</span>
            <p className="text-discord-faint text-xs">AI Content Studio</p>
          </div>
        </div>

        {/* Creator info */}
        {creatorProfile && (
          <div className="px-3 py-3 border-b border-discord-faint/20">
            <div className="flex items-center gap-2.5 px-2 py-2 rounded-lg bg-discord-input/50">
              <div className="w-8 h-8 rounded-full bg-discord-blurple flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                {creatorProfile.name?.[0]?.toUpperCase() || 'C'}
              </div>
              <div className="min-w-0">
                <p className="text-discord-white text-xs font-semibold truncate">{creatorProfile.handle}</p>
                <p className="text-discord-muted text-xs truncate">{creatorProfile.niche}</p>
              </div>
            </div>
          </div>
        )}

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto px-2 py-3 space-y-0.5">
          <p className="text-discord-faint text-xs font-semibold uppercase tracking-wider px-2 mb-2">Workflow</p>
          {NAV_ITEMS.map(({ screen: s, label, icon: Icon }) => {
            const unlocked = isUnlocked(s, { creatorProfile, selectedTopic, selectedVariant, productionPlan })
            const active   = screen === s
            return (
              <button
                key={s}
                onClick={() => unlocked && navigate(s)}
                disabled={!unlocked}
                title={!unlocked ? `${label} — complete previous steps to unlock` : label}
                className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-sm font-medium transition-all duration-150
                  ${active
                    ? 'bg-discord-blurple/20 text-discord-white'
                    : unlocked
                      ? 'text-discord-muted hover:bg-discord-hover hover:text-discord-white'
                      : 'text-discord-faint/35 cursor-not-allowed'
                  }`}
              >
                <Icon size={16} className={active ? 'text-discord-blurple' : ''} />
                <span className="flex-1 text-left">{label}</span>
                {active   && <ChevronRight size={14} className="text-discord-blurple" />}
                {!unlocked && <span className="text-discord-faint/40 text-xs">🔒</span>}
              </button>
            )
          })}
        </nav>

        {/* Sign out */}
        <div className="px-3 py-3 border-t border-discord-faint/20">
          <button
            onClick={logout}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-sm text-discord-muted hover:text-discord-red hover:bg-discord-red/10 transition-all"
          >
            <LogOut size={16} />
            Sign out
          </button>
        </div>
      </aside>

      {/* ── Main area ────────────────────────────────────────────────────────── */}
      <main className="flex flex-col flex-1 min-w-0 overflow-hidden bg-discord-bg">

        {/* Top header bar */}
        <header className="flex-shrink-0 flex items-center gap-2 px-5 h-12 bg-discord-bg border-b border-discord-faint/20 shadow-sm z-10">
          <Hash size={16} className="text-discord-muted" />
          <span className="text-discord-white font-semibold text-sm">{headerLabel}</span>
          {selectedTopic && ['script', 'production', 'output', 'xml-export', 'video-gen', 'publish'].includes(screen) && (
            <>
              <span className="text-discord-faint/50 mx-1">·</span>
              <span className="text-discord-muted text-xs truncate max-w-xs">{selectedTopic.topic}</span>
            </>
          )}
        </header>

        {/* Page content */}
        <div className="flex-1 overflow-y-auto">
          {children}
        </div>
      </main>
    </div>
  )
}
