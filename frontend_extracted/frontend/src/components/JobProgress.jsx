// ─────────────────────────────────────────────────────────────────────────────
// JobProgress: the card shown while a long job runs (writing scripts, building
// a profile, researching trends, exporting XML, rendering video).
//
//   header    icon · title · "Step 3 of 6 · …" · live elapsed time
//   bar       overall progress with a moving shimmer
//   timeline  done steps (✓ + how long they took), the active step (pulsing,
//             with its live detail), upcoming steps (faint)
//   footer    a short note on what is happening / what comes next
//
// `error` turns the card into an error state with an optional `action` button.
// ─────────────────────────────────────────────────────────────────────────────
import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, Check, Info } from 'lucide-react'
import { EASE, motion } from './motion'

const cx = (...c) => c.filter(Boolean).join(' ')
const mmss = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
const short = (s) => (s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`)

export default function JobProgress({ icon: Icon, title, steps, currentStep, detail, hint, error, action, className = '' }) {
  const started = useRef(Date.now())
  const stepStarts = useRef({})          // step index → ms when it became active
  const [now, setNow] = useState(Date.now())

  // remember when each step started, to show how long finished steps took
  const current = Math.max(0, Math.min(currentStep, steps.length - 1))
  if (stepStarts.current[current] === undefined) stepStarts.current[current] = Date.now()

  useEffect(() => {
    if (error) return undefined
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [error])

  const elapsed = Math.max(0, Math.round((now - started.current) / 1000))
  const pct = Math.min(97, Math.round(((current + 0.5) / steps.length) * 100))
  const tookFor = (i) => {
    const a = stepStarts.current[i]
    const b = stepStarts.current[i + 1]
    return a !== undefined && b !== undefined ? short(Math.max(1, Math.round((b - a) / 1000))) : null
  }

  return (
    <div className={cx('max-w-3xl overflow-hidden rounded-2xl border-2 bg-vh-surface',
      error ? 'border-vh-accent2 shadow-[6px_6px_0_0_rgb(var(--vh-accent2))]' : 'border-vh-night shadow-hard', className)} role="status" aria-live="polite">

      {/* header */}
      <div className="flex items-start gap-4 p-6 pb-5">
        <span className={cx('relative flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border-2 border-vh-night',
          error ? 'bg-vh-accent2 text-white' : 'bg-vh-accent text-vh-ink')}>
          {error ? <AlertTriangle size={22} /> : Icon && <Icon size={22} strokeWidth={2} />}
        </span>
        <div className="min-w-0 flex-1">
          <p className="display text-[1.9rem] text-vh-head">{error ? 'Something went wrong' : title}</p>
          <p className="mt-0.5 truncate text-sm text-vh-text">
            {error ? `Stopped at: ${steps[current]?.label}` : <>Step <span className="font-bold text-vh-accent2">{current + 1}</span> of {steps.length} · {steps[current]?.label}</>}
          </p>
        </div>
        <span className="shrink-0 rounded-md bg-vh-night px-2.5 py-1 font-mono text-xs font-semibold text-vh-cream tabular" title="Elapsed">{mmss(elapsed)}</span>
      </div>

      {/* overall progress */}
      <div className="px-6">
        <div className="relative h-3 overflow-hidden rounded-full border-2 border-vh-night bg-vh-raised">
          <motion.div className={cx('relative h-full overflow-hidden', error ? 'bg-vh-accent2' : 'bg-vh-accent')}
            initial={false} animate={{ width: `${pct}%` }} transition={{ duration: 0.8, ease: EASE }}>
            {!error && <span className="absolute inset-y-0 w-1/2 animate-shimmer bg-gradient-to-r from-transparent via-white/60 to-transparent" />}
          </motion.div>
        </div>
        <p className="mt-1.5 text-right font-mono text-[11px] font-semibold text-vh-text tabular">{pct}%</p>
      </div>

      {/* step timeline */}
      <ol className="px-6 pb-6 pt-2">
        {steps.map((step, i) => {
          const done = i < current
          const active = i === current
          const last = i === steps.length - 1
          return (
            <li key={step.id || i} className="relative flex gap-4 pb-4 last:pb-0">
              {!last && (
                <span aria-hidden="true" className="absolute left-[13px] top-8 h-[calc(100%-1.5rem)] w-0.5 overflow-hidden rounded-full bg-vh-night/15">
                  <motion.span className="block w-full bg-vh-night" initial={false}
                    animate={{ height: done ? '100%' : '0%' }} transition={{ duration: 0.5, ease: EASE }} />
                </span>
              )}
              <span className={cx('relative z-10 mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2 transition-colors',
                done ? 'border-vh-night bg-vh-night text-vh-cream'
                  : active ? (error ? 'border-vh-accent2 bg-vh-accent2 text-white' : 'border-vh-night bg-vh-accent text-vh-ink') : 'border-vh-night/30 bg-vh-surface text-vh-text')}>
                {done ? <Check size={14} strokeWidth={3} />
                  : active ? (error ? <AlertTriangle size={12} /> : <span className="h-2 w-2 animate-pulse rounded-full bg-vh-night" />)
                    : <span className="font-mono text-[10px] font-semibold">{i + 1}</span>}
                {active && !error && <span className="absolute -inset-1 animate-ping rounded-full border-2 border-vh-accent [animation-duration:1.8s]" />}
              </span>
              <div className="min-w-0 flex-1 pt-1">
                <div className="flex items-baseline justify-between gap-3">
                  <span className={cx('text-[15px]', active ? 'font-bold text-vh-strong' : done ? 'font-medium text-vh-text' : 'text-vh-text')}>{step.label}</span>
                  {done && tookFor(i) && <span className="shrink-0 font-mono text-[11px] text-vh-text tabular">{tookFor(i)}</span>}
                </div>
                {active && detail && !error && (
                  <motion.p key={detail} initial={{ opacity: 0, y: -2 }} animate={{ opacity: 1, y: 0 }}
                    className="mt-1 truncate font-mono text-xs text-vh-text">{detail}</motion.p>
                )}
              </div>
            </li>
          )
        })}
      </ol>

      {/* footer */}
      {(error || hint) && (
        <div className={cx('flex flex-wrap items-center gap-3 border-t-2 px-6 py-4 text-sm font-medium',
          error ? 'border-vh-accent2 bg-vh-accent2/[0.07] text-vh-text' : 'border-vh-night bg-vh-raised text-vh-text')}>
          {!error && <Info size={16} className="shrink-0" />}
          <span className="min-w-0 flex-1">{error || hint}</span>
          {error && action}
        </div>
      )}
    </div>
  )
}
