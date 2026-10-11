import { Sparkles, TrendingUp, ChevronRight } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { Btn } from '../../components/ui'

const TYPES = [
  {
    id: 'new',
    icon: Sparkles,
    title: 'New Creator',
    subtitle: "I'm just getting started",
    description: "Tell us your niche and content preferences. We'll build your initial style profile and help you create your first viral-ready content.",
    bullets: ['Quick niche setup', 'Style profile from preferences', 'Jump straight into content creation'],
    color: 'text-discord-green',
    bg: 'bg-discord-green/10',
    border: 'hover:border-discord-green/60',
    screen: 'onboarding-new',
  },
  {
    id: 'experienced',
    icon: TrendingUp,
    title: 'Experienced Creator',
    subtitle: 'I have existing content',
    description: "Upload your past videos. We'll analyse your transcripts, extract your unique style, hooks, and structure to create a personalised creator profile.",
    bullets: ['Upload historical videos', 'AI-powered style extraction', 'Personalised creator knowledge base'],
    color: 'text-discord-blurple',
    bg: 'bg-discord-blurple/10',
    border: 'hover:border-discord-blurple/60',
    screen: 'onboarding-experienced',
  },
]

export default function CreatorTypeScreen() {
  const { navigate } = useApp()

  return (
    <div className="flex h-screen w-screen bg-discord-dark items-center justify-center p-6">
      <div className="w-full max-w-2xl">
        <div className="text-center mb-10">
          <h1 className="text-discord-white font-bold text-3xl mb-2">What kind of creator are you?</h1>
          <p className="text-discord-muted text-base">Choose how you want to get started with ViralHook.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {TYPES.map(({ id, icon: Icon, title, subtitle, description, bullets, color, bg, border, screen }) => (
            <button
              key={id}
              onClick={() => navigate(screen)}
              className={`
                flex flex-col text-left p-6 rounded-2xl
                bg-discord-sidebar border border-discord-faint/25
                ${border} hover:shadow-xl hover:-translate-y-1
                transition-all duration-200 group
              `}
            >
              <div className={`inline-flex items-center justify-center w-12 h-12 rounded-xl ${bg} mb-4`}>
                <Icon size={24} className={color} />
              </div>
              <h2 className="text-discord-white font-bold text-lg mb-0.5">{title}</h2>
              <p className={`text-sm font-medium mb-3 ${color}`}>{subtitle}</p>
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
                Get started <ChevronRight size={16} />
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
