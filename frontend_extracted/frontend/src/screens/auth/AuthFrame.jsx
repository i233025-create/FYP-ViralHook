// Shared layout of the signed-out account screens (sign in, sign up, forgot /
// reset password, verify email): black top bar, cream page with lock / mail
// line art, the poster's clapperboard card on the left and the form on the right.
import { PageDecor } from '../../components/art'
import Logo from '../../components/brand/Logo'
import { StepChip } from '../../components/ui'

export default function AuthFrame({ headerRight, children, chip = 'Account' }) {
  return (
    <div className="flex min-h-[100dvh] flex-col">
      <header className="on-dark shrink-0 bg-vh-night">
        <div className="mx-auto flex h-[4.5rem] max-w-[90rem] items-center justify-between gap-3 px-4 sm:px-8">
          <Logo />
          <div className="flex items-center gap-3 text-[15px]">{headerRight}</div>
        </div>
        <div className="mx-auto max-w-[90rem] px-4 pb-3 sm:px-8"><div className="sprockets" aria-hidden="true" /></div>
      </header>

      <main className="relative isolate flex flex-1 items-start justify-center overflow-hidden px-4 pb-48 pt-10 sm:px-8 lg:items-center lg:pt-12">
        <PageDecor kind="auth" />
        <div className="grid w-full max-w-5xl items-center gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,27rem)]">
          <PosterCard chip={chip} />
          <div className="mx-auto w-full max-w-[27rem] animate-rise">{children}</div>
        </div>
      </main>
    </div>
  )
}

/** Clapperboard card from the poster: tagline + the idea → reel steps. */
function PosterCard({ chip }) {
  const steps = [['01', 'Learn', 'your style from past reels'], ['02', 'Create', 'scripts that sound like you'], ['03', 'Post', 'a finished, on-brand reel']]
  return (
    <section className="on-dark hidden overflow-hidden rounded-2xl bg-vh-night shadow-accent lg:block">
      <div className="clapper h-11" aria-hidden="true" />
      <div className="px-9 pb-10 pt-7">
        <StepChip label={chip} />
        <h1 className="mt-5">
          <span className="display block text-[5.4rem] text-vh-cream">Your voice.</span>
          <span className="display block text-[5.4rem] text-vh-accent">Every video.</span>
        </h1>
        <p className="mt-4 font-mono text-[14px] uppercase tracking-[0.1em] text-vh-accent">Multi-agent GenAI · Idea → Reel</p>
        <ol className="mt-8 space-y-3">
          {steps.map(([n, t, d]) => (
            <li key={n} className="flex items-center gap-4 rounded-xl bg-vh-frame px-4 py-3">
              <span className="display w-9 text-[2rem] text-vh-accent">{n}</span>
              <span className="display text-[1.8rem]">{t}</span>
              <span className="text-[15px]">{d}</span>
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}

/** Form card title: plain word + mustard-boxed word. */
export function AuthTitle({ plain, highlight, sub }) {
  return (
    <div className="mb-6">
      <h2 className="display text-[3.4rem] leading-[1.02]">
        {plain}{highlight && ' '}
        {highlight && <span className="rounded-md bg-vh-accent px-[0.12em] pt-[0.1em]">{highlight}</span>}
      </h2>
      {sub && <p className="mt-2 text-[16px] leading-relaxed">{sub}</p>}
    </div>
  )
}
