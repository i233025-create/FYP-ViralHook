import { FileCode, Sparkles, ChevronRight } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { Card, SectionHeader, Page } from '../../components/ui'

const OPTIONS = [
  {
    id: 'xml',
    icon: FileCode,
    title: 'Export Editable XML',
    subtitle: 'Premiere Pro project file',
    description: 'Create a fully structured Adobe Premiere Pro timeline with clips, captions, audio tracks, and timestamps. Import directly and start editing.',
    bullets: [
      'Complete timeline structure',
      'Scene clips with timecodes',
      'Caption / text overlay layer',
      'Voiceover audio track slots',
      'Scene markers',
    ],
    color: 'text-discord-link',
    bg: 'bg-discord-link/10',
    border: 'hover:border-discord-link/50',
    screen: 'xml-export',
  },
  {
    id: 'video',
    icon: Sparkles,
    title: 'Generate AI Video',
    subtitle: 'AI-rendered preview (prototype)',
    description: 'Generate a video from your structured production timeline. Visual assets, captions, and voiceover slots assembled into a preview you can refine scene by scene.',
    bullets: [
      'JSON timeline → video preview',
      'Per-scene visual asset selection',
      'Inline subtitle editing',
      'Scene timing adjustments',
      'Future: FFmpeg MP4 rendering',
    ],
    color: 'text-purple-400',
    bg: 'bg-purple-500/10',
    border: 'hover:border-purple-500/40',
    screen: 'video-gen',
    badge: 'Prototype',
  },
]

export default function OutputChoiceScreen() {
  const { navigate } = useApp()

  return (
    <Page>
      <div className="max-w-2xl mx-auto">
        <SectionHeader
          icon={FileCode}
          title="How do you want to output your video?"
          subtitle="Choose your production path."
        />

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {OPTIONS.map(({ id, icon: Icon, title, subtitle, description, bullets, color, bg, border, screen, badge }) => (
            <button
              key={id}
              onClick={() => navigate(screen)}
              className={`flex flex-col text-left p-6 rounded-2xl bg-discord-sidebar border border-discord-faint/25 ${border} hover:shadow-xl hover:-translate-y-1 transition-all duration-200 group`}
            >
              <div className={`inline-flex items-center justify-center w-12 h-12 rounded-xl ${bg} mb-4 flex-shrink-0`}>
                <Icon size={24} className={color} />
              </div>
              <div className="flex items-center gap-2 mb-0.5">
                <h3 className="text-discord-white font-bold text-base">{title}</h3>
                {badge && <span className="px-1.5 py-0.5 bg-purple-500/20 text-purple-400 text-xs rounded border border-purple-500/30">{badge}</span>}
              </div>
              <p className={`text-xs font-medium mb-3 ${color}`}>{subtitle}</p>
              <p className="text-discord-muted text-sm leading-relaxed mb-4">{description}</p>
              <ul className="space-y-1.5 mb-5">
                {bullets.map((b) => (
                  <li key={b} className="flex items-center gap-2 text-discord-muted text-xs">
                    <span className={`w-1 h-1 rounded-full flex-shrink-0 ${color.replace('text-', 'bg-')}`} />
                    {b}
                  </li>
                ))}
              </ul>
              <div className={`flex items-center gap-1 text-sm font-semibold mt-auto ${color} group-hover:gap-2 transition-all`}>
                Choose this <ChevronRight size={16} />
              </div>
            </button>
          ))}
        </div>
      </div>
    </Page>
  )
}
