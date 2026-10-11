import { Upload, User, Lightbulb, Download, Home } from 'lucide-react'
import { PHASES } from '../phases'

const PHASE_META = {
  [PHASES.LANDING]:   { icon: Home,       label: 'Home',       color: 'text-discord-blurple' },
  [PHASES.UPLOAD]:    { icon: Upload,      label: 'Upload',     color: 'text-discord-green' },
  [PHASES.PROFILE]:   { icon: User,        label: 'Profile',    color: 'text-discord-yellow' },
  [PHASES.IDEATION]:  { icon: Lightbulb,   label: 'Ideation',   color: 'text-purple-400' },
  [PHASES.EXPORT]:    { icon: Download,    label: 'Export',     color: 'text-discord-link' },
}

// Which phases are "unlocked" depends on what data exists
function isUnlocked(phase, { uploadedVideos, creatorProfile, scripts }) {
  switch (phase) {
    case PHASES.LANDING:  return true
    case PHASES.UPLOAD:   return true
    case PHASES.PROFILE:  return uploadedVideos.length > 0
    case PHASES.IDEATION: return !!creatorProfile
    case PHASES.EXPORT:   return scripts.length > 0
    default:              return false
  }
}

export default function Sidebar({ currentPhase, goToPhase, phaseOrder, phases, uploadedVideos, creatorProfile, scripts }) {
  return (
    <div className="flex flex-col items-center w-[72px] min-w-[72px] bg-discord-darker py-3 gap-2 overflow-y-auto z-10">
      {/* Logo / brand pill */}
      <div className="flex items-center justify-center w-12 h-12 rounded-[24px] bg-discord-blurple hover:rounded-[16px] transition-all duration-200 cursor-pointer mb-1 shadow-lg">
        <span className="text-white font-bold text-lg select-none">VH</span>
      </div>

      {/* Divider */}
      <div className="w-8 h-px bg-discord-faint rounded-full" />

      {/* Phase navigation icons */}
      {phaseOrder.filter(p => p !== PHASES.LANDING).map((phase) => {
        const meta = PHASE_META[phase]
        const Icon = meta.icon
        const active = currentPhase === phase
        const unlocked = isUnlocked(phase, { uploadedVideos, creatorProfile, scripts })

        return (
          <div key={phase} className="relative group">
            <button
              onClick={() => unlocked && goToPhase(phase)}
              disabled={!unlocked}
              className={`
                flex items-center justify-center w-12 h-12 rounded-[24px]
                transition-all duration-200
                ${active
                  ? 'rounded-[16px] bg-discord-blurple text-white shadow-lg'
                  : unlocked
                    ? 'bg-discord-sidebar hover:rounded-[16px] hover:bg-discord-blurple text-discord-muted hover:text-white'
                    : 'bg-discord-sidebar text-discord-faint cursor-not-allowed opacity-40'
                }
              `}
            >
              <Icon size={20} />
            </button>

            {/* Active indicator pill */}
            {active && (
              <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-white rounded-r-full -ml-3" />
            )}

            {/* Tooltip */}
            <div className="
              absolute left-16 top-1/2 -translate-y-1/2
              bg-discord-darker text-discord-text text-sm font-semibold
              px-3 py-1.5 rounded-md shadow-xl
              whitespace-nowrap pointer-events-none
              opacity-0 group-hover:opacity-100
              transition-opacity duration-150 z-50
              border border-discord-faint
            ">
              {meta.label}
              {!unlocked && <span className="ml-1 text-discord-muted text-xs">(locked)</span>}
              <span className="absolute right-full top-1/2 -translate-y-1/2 border-4 border-transparent border-r-discord-darker" />
            </div>
          </div>
        )
      })}
    </div>
  )
}
