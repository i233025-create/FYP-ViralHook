import {
  ArrowRight, Gauge, ShieldCheck, Sparkles, Upload, Database, TrendingUp, PenLine, CircleCheck, Video, Send, Clock,
  Heart, MessageCircle,
} from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { Btn, StepChip } from '../../components/ui'
import Logo, { LogoMark } from '../../components/brand/Logo'
import { PageDecor } from '../../components/art'
import { Reveal, Stagger, StaggerItem } from '../../components/motion'

/** Header for signed-out pages (landing, public pricing): black bar + sprocket row. */
export function PublicHeader() {
  const { navigate } = useApp()
  return (
    <header className="on-dark relative z-40 bg-vh-night">
      <div className="mx-auto flex h-[4.5rem] max-w-[90rem] items-center justify-between gap-3 px-4 sm:px-8">
        <button type="button" onClick={() => navigate('landing')} aria-label="ViralHook home"><Logo /></button>
        <nav className="flex items-center gap-1 sm:gap-3">
          <Btn variant="ghost" size="sm" className="hidden sm:inline-flex" onClick={() => navigate('pricing')}>Pricing</Btn>
          <Btn variant="ghost" size="sm" onClick={() => navigate('auth')}>Sign in</Btn>
          <Btn size="sm" onClick={() => navigate('auth-signup')}>Start free</Btn>
        </nav>
      </div>
      <div className="mx-auto max-w-[90rem] px-4 pb-3 sm:px-8"><div className="sprockets" aria-hidden="true" /></div>
    </header>
  )
}

// The poster's system workflow, as the five frames of a film strip
const AGENTS = [
  [TrendingUp, 'YouTube Data API', 'Trend agent'],
  [PenLine, 'Qwen2.5 · Ollama', 'Script agent'],
  [CircleCheck, 'Rubric scoring', 'Evaluator'],
  [Video, 'SDXL · TTS · FFmpeg', 'Video engine'],
  [Send, 'Instagram or Premiere XML', 'Publisher'],
]

const PROMISES = [
  [Gauge, 'Honest numbers', 'Every score is measured. If we cannot measure it, we show —, never a guess.'],
  [ShieldCheck, 'Your data stays yours', 'Your videos and profile live in your own workspace, nobody else sees them.'],
  [Sparkles, 'Your voice, not a template', 'Scripts are written from your real transcripts, not generic AI copy.'],
]

export default function LandingScreen() {
  const { navigate } = useApp()
  return (
    <div className="min-h-[100dvh]">
      <PublicHeader />

      <div className="relative isolate overflow-hidden">
        <PageDecor kind="landing" />
        <div className="mx-auto max-w-page px-4 pb-48 pt-10 sm:px-8 sm:pt-14">

          {/* hero: the poster's clapperboard */}
          <section className="on-dark overflow-hidden rounded-2xl bg-vh-night shadow-accent">
            <div className="clapper h-10 sm:h-12" aria-hidden="true" />
            <div className="grid items-center gap-10 px-6 pb-10 pt-8 sm:px-10 lg:grid-cols-[minmax(0,1fr)_17rem]">
              <Stagger gap={0.08}>
                <StaggerItem><StepChip label="AI studio for reel creators" /></StaggerItem>
                <StaggerItem as="h1" className="mt-5">
                  <span className="display block text-[clamp(3.6rem,10vw,7.4rem)] text-vh-cream">Your voice.</span>
                  <span className="display block text-[clamp(3.6rem,10vw,7.4rem)] text-vh-accent">Every video.</span>
                </StaggerItem>
                <StaggerItem as="p" className="mt-4 font-mono text-[14px] uppercase tracking-[0.1em] text-vh-accent">Multi-agent GenAI · Idea → Reel</StaggerItem>
                <StaggerItem as="p" className="mt-5 max-w-xl text-[17px] leading-relaxed">
                  ViralHook learns how you make reels, finds what's working in your niche, and writes scripts that sound like you — then turns them into a video.
                </StaggerItem>
                <StaggerItem className="mt-8 flex flex-wrap gap-3">
                  <Btn size="lg" iconRight={ArrowRight} onClick={() => navigate('auth-signup')}>Start free</Btn>
                  <Btn size="lg" variant="secondary" onClick={() => navigate('pricing')}>See pricing</Btn>
                </StaggerItem>
                <StaggerItem as="p" className="mt-4 font-mono text-[13px]">Free plan · no card needed</StaggerItem>
              </Stagger>
              <ReelPhone />
            </div>
          </section>

          {/* how it works: the system workflow */}
          <section className="mt-20">
            <Reveal>
              <h2 className="display text-[clamp(2.6rem,5vw,4rem)]">How it <span className="rounded-md bg-vh-accent px-[0.12em] pt-[0.1em]">works</span></h2>
            </Reveal>

            <Reveal className="mt-8 grid gap-4 md:grid-cols-[auto_auto_minmax(0,1fr)] md:items-stretch">
              <SmallStep icon={Upload} kicker="Upload" title="Past reels" />
              <SmallStep icon={Database} kicker="Whisper · MiniLM · Qdrant" title="Style memory" />
              <div className="flex items-center gap-4 rounded-2xl border-2 border-l-[10px] border-vh-night border-l-vh-accent2 bg-white px-5 py-4">
                <Clock size={28} className="shrink-0 text-vh-accent2" />
                <div>
                  <p className="font-mono text-[12px] font-bold uppercase tracking-[0.08em] text-vh-accent2">The problem</p>
                  <p className="mt-0.5 text-[16px] font-semibold leading-snug">One reel takes hours of scripting and editing, and generic AI tools ignore the creator's own style.</p>
                </div>
              </div>
            </Reveal>

            <Reveal className="mt-6 rounded-2xl bg-vh-night px-3 py-4 sm:px-5">
              <div className="sprockets" aria-hidden="true" />
              <ol className="my-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                {AGENTS.map(([Icon, tech, name], i) => (
                  <li key={name} className="flex flex-col rounded-lg bg-vh-cream px-4 py-4">
                    <span className="flex items-center justify-between">
                      <Icon size={24} className="text-vh-accent2" strokeWidth={2.25} />
                      <span className="font-mono text-[12px] font-bold">0{i + 1}</span>
                    </span>
                    <span className="mt-4 font-mono text-[11px] font-semibold uppercase tracking-[0.04em] text-vh-accent2">{tech}</span>
                    <span className="display mt-1 text-[2rem] leading-none">{name}</span>
                  </li>
                ))}
              </ol>
              <div className="sprockets" aria-hidden="true" />
            </Reveal>

            <Reveal className="mt-4 rounded-2xl bg-vh-accent px-6 py-4">
              <p className="text-[16px] font-medium"><span className="display mr-2 text-[2rem] align-[-3px]">Human-in-the-loop</span>· you review and approve the output of every agent</p>
            </Reveal>
          </section>

          {/* promises */}
          <Stagger className="mt-20 grid gap-6 md:grid-cols-3">
            {PROMISES.map(([Icon, title, text]) => (
              <StaggerItem key={title} className="rounded-2xl border-2 border-vh-night bg-white p-6 shadow-hard">
                <span className="flex h-12 w-12 items-center justify-center rounded-xl border-2 border-vh-night bg-vh-accent"><Icon size={22} /></span>
                <h3 className="display mt-5 text-[2.1rem]">{title}</h3>
                <p className="mt-1 text-[16px] leading-relaxed">{text}</p>
              </StaggerItem>
            ))}
          </Stagger>

          {/* final call to action */}
          <Reveal className="on-dark mt-20 overflow-hidden rounded-2xl bg-vh-night text-center shadow-accent">
            <div className="clapper h-9" aria-hidden="true" />
            <div className="px-6 py-12">
              <LogoMark title="" className="mx-auto h-14 w-auto text-vh-accent" />
              <h2 className="display mt-5 text-[clamp(2.6rem,5.4vw,4.4rem)]">Make your next reel <span className="text-vh-accent">sound like you</span></h2>
              <p className="mx-auto mt-3 max-w-md text-[16px]">Start free with 5 scripts and 3 research runs every month.</p>
              <div className="mt-8 flex justify-center"><Btn size="lg" iconRight={ArrowRight} onClick={() => navigate('auth-signup')}>Start free</Btn></div>
            </div>
          </Reveal>
        </div>
      </div>

      <footer className="on-dark bg-vh-night">
        <div className="mx-auto flex max-w-[90rem] flex-wrap items-center justify-between gap-3 px-4 py-7 sm:px-8">
          <Logo />
          <span className="font-mono text-[13px] text-vh-cream">© {new Date().getFullYear()} ViralHook · Final Year Project</span>
        </div>
      </footer>
    </div>
  )
}

function SmallStep({ icon: Icon, kicker, title }) {
  return (
    <div className="flex items-center gap-4 rounded-2xl border-2 border-vh-night bg-white px-5 py-4">
      <Icon size={26} className="shrink-0 text-vh-accent2" />
      <div>
        <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.04em] text-vh-accent2">{kicker}</p>
        <p className="display text-[1.9rem] leading-none">{title}</p>
      </div>
    </div>
  )
}

/** The poster's reel mock-up: a phone with a mustard reel, a caption and side actions. */
function ReelPhone() {
  return (
    <div className="mx-auto hidden w-[17rem] rounded-[2rem] border-[5px] border-vh-cream/90 bg-vh-night p-4 sm:block" aria-hidden="true">
      <p className="font-mono text-[12px] font-bold tracking-[0.1em] text-vh-accent">REELS</p>
      <div className="mt-3 flex gap-3">
        <div className="relative h-[19rem] flex-1 overflow-hidden rounded-xl bg-vh-accent">
          <span className="absolute left-2 top-2 rounded bg-vh-cream px-1.5 py-0.5 font-mono text-[9px] font-bold text-vh-night">● REC 0:12</span>
          <span className="absolute left-1/2 top-12 h-24 w-24 -translate-x-1/2 rounded-full border-[5px] border-vh-cream/90" />
          <span className="absolute left-1/2 top-[4.3rem] h-12 w-12 -translate-x-1/2 rounded-full bg-vh-night" />
          <span className="absolute -bottom-6 left-1/2 h-36 w-32 -translate-x-1/2 rounded-t-full bg-vh-night" />
          <p className="display absolute inset-x-2 bottom-12 text-center text-[1.55rem] leading-[1.02] text-vh-cream">
            This reel sounds like <span className="bg-vh-accent2 px-1">me</span>, not a bot
          </p>
          <span className="absolute inset-x-3 bottom-3 rounded-full bg-vh-night/85 px-2 py-1 text-center font-mono text-[8px] text-vh-cream">AI voice-over · @creator</span>
        </div>
        <div className="flex flex-col justify-end gap-4 pb-6 text-vh-cream">
          {[[Heart, 'Learn'], [MessageCircle, 'Create'], [Send, 'Post']].map(([Icon, l]) => (
            <span key={l} className="flex flex-col items-center gap-0.5"><Icon size={20} /><span className="font-mono text-[8px] text-vh-accent">{l}</span></span>
          ))}
        </div>
      </div>
      <p className="mt-3 font-mono text-[11px] font-bold text-vh-accent">@viralhook · FOLLOW</p>
      <div className="mt-2 h-1 overflow-hidden rounded-full bg-vh-frame"><div className="h-full w-1/2 bg-gradient-to-r from-vh-accent2 to-vh-accent" /></div>
    </div>
  )
}
