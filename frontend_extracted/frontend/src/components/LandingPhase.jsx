import { Zap, TrendingUp, FileText, Video } from 'lucide-react'
import { PHASES } from '../phases'

const FEATURES = [
  {
    icon: Video,
    title: 'Style Extraction',
    desc: 'Upload your existing videos. We transcribe and analyse them to learn your unique voice, hooks, and pacing.',
    color: 'text-discord-green',
    bg: 'bg-discord-green/10',
  },
  {
    icon: TrendingUp,
    title: 'Trend Discovery',
    desc: 'Real-time YouTube trend scoring — velocity, engagement, topic clustering — finds exactly what your niche is watching.',
    color: 'text-purple-400',
    bg: 'bg-purple-400/10',
  },
  {
    icon: FileText,
    title: 'Script Generation',
    desc: 'Three personalised scripts per session using your style profile and trending topics, with an evaluator feedback loop.',
    color: 'text-discord-link',
    bg: 'bg-discord-link/10',
  },
  {
    icon: Zap,
    title: 'Premiere Export',
    desc: 'One click exports a fully structured Adobe Premiere Pro XML with timecodes, captions, and voiceover slots ready to edit.',
    color: 'text-discord-yellow',
    bg: 'bg-discord-yellow/10',
  },
]

export default function LandingPhase({ goToPhase }) {
  return (
    <div className="flex flex-col items-center justify-center h-full w-full bg-discord-bg overflow-y-auto px-6 py-12 animate-fade-in">
      {/* Hero */}
      <div className="flex flex-col items-center text-center mb-14 max-w-2xl">
        {/* Badge */}
        <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-discord-blurple/20 border border-discord-blurple/40 text-discord-blurple text-xs font-semibold mb-6">
          <Zap size={12} />
          AI-Powered Short-Form Video Studio
        </div>

        {/* Title */}
        <h1 className="text-5xl font-bold text-discord-white leading-tight mb-4">
          Viral<span className="text-discord-blurple">Hook</span>
        </h1>
        <p className="text-discord-muted text-lg leading-relaxed mb-8 max-w-lg">
          From your existing videos to a ready-to-edit Premiere Pro file in minutes.
          Upload, profile, trend-match, script, export.
        </p>

        {/* CTA */}
        <button
          onClick={() => goToPhase(PHASES.UPLOAD)}
          className="
            flex items-center gap-3 px-8 py-4
            bg-discord-blurple hover:bg-discord-blurple_hover
            text-white font-semibold text-lg rounded-lg
            shadow-lg hover:shadow-discord-blurple/30 hover:shadow-2xl
            transform hover:-translate-y-0.5
            transition-all duration-200
          "
        >
          <Zap size={20} />
          Let's Start
        </button>
      </div>

      {/* Feature cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-2xl w-full">
        {FEATURES.map(({ icon: Icon, title, desc, color, bg }) => (
          <div
            key={title}
            className="
              flex gap-4 p-5 rounded-lg
              bg-discord-sidebar border border-discord-faint/30
              hover:border-discord-faint/60
              transition-colors duration-200
            "
          >
            <div className={`flex-shrink-0 flex items-center justify-center w-10 h-10 rounded-lg ${bg}`}>
              <Icon size={20} className={color} />
            </div>
            <div>
              <h3 className="text-discord-white font-semibold text-sm mb-1">{title}</h3>
              <p className="text-discord-muted text-xs leading-relaxed">{desc}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Footer note */}
      <p className="mt-10 text-discord-faint text-xs">
        Final Year Project — ViralHook v1.0 POC
      </p>
    </div>
  )
}
