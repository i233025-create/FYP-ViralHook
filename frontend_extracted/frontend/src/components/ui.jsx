// ─────────────────────────────────────────────────────────────────────────────
// VIRALHOOK — UI KIT  ("mustard studio" theme, ui_demo/)
// Small, consistent building blocks. Colours only through vh-* theme tokens.
// Inside a black panel (class "on-dark", e.g. <Card tone="dark">) the same
// components switch to cream-on-black automatically (see index.css).
//
//   Layout   Page, PageHero, Checklist, ActionBar, SectionTitle, EmptyState
//   Actions  Btn, IconBtn
//   Content  Card, Tile, Badge, SegmentTag, ScoreBar, Stat, InfoTip, ProgressSteps
//   Forms    Input, Textarea, Select, Field
//   Feedback Alert, Spinner, Modal, Divider
// ─────────────────────────────────────────────────────────────────────────────
import { forwardRef, useEffect, useId, useState } from 'react'
import { createPortal } from 'react-dom'
import { Check, X, AlertTriangle, Info, CircleCheck, Circle } from 'lucide-react'
import { PageDecor } from './art'
import { AnimatePresence, CountUp, EASE, Stagger, StaggerItem, motion } from './motion'

const cx = (...c) => c.filter(Boolean).join(' ')

// ── Buttons ───────────────────────────────────────────────────────────────────
const BTN_SIZES = {
  sm: 'h-9 px-3.5 text-[13px] gap-1.5 rounded-lg',
  md: 'h-11 px-5 text-sm gap-2 rounded-xl',
  lg: 'h-14 px-7 text-[15px] gap-2.5 rounded-xl uppercase tracking-[0.06em]',
}
const BTN_VARIANTS = {
  // mustard; black outline on cream/white, none on black panels
  primary:   'bg-vh-accent text-vh-ink border-2 border-vh-night [.on-dark_&]:border-vh-accent hover:bg-vh-accent-hover font-bold hover:-translate-y-px',
  // outlined: black on cream, cream on black
  secondary: 'bg-transparent text-vh-head border-2 border-vh-edge hover:bg-vh-raised font-semibold',
  // cream button (used on black cards)
  light:     'bg-vh-cream text-vh-night border-2 border-vh-cream hover:bg-white font-semibold',
  // solid black
  dark:      'bg-vh-night text-vh-cream border-2 border-vh-night hover:bg-vh-frame font-semibold',
  ghost:     'bg-transparent text-vh-head hover:bg-vh-raised font-semibold underline-offset-4 hover:underline',
  danger:    'bg-transparent text-vh-bad border-2 border-vh-bad hover:bg-vh-bad hover:text-white font-semibold',
  // kept for older call sites
  outline:   'bg-transparent text-vh-head border-2 border-vh-edge hover:bg-vh-raised font-semibold',
  success:   'bg-vh-night text-vh-cream border-2 border-vh-night font-semibold',
}

export function Btn({
  children, onClick, variant = 'primary', size = 'md', disabled = false, loading = false,
  className = '', type = 'button', icon: Icon, iconRight: IconRight, title,
}) {
  const iconSize = size === 'sm' ? 14 : size === 'lg' ? 18 : 16
  return (
    <button
      type={type}
      onClick={onClick}
      title={title}
      disabled={disabled || loading}
      className={cx(
        'inline-flex items-center justify-center whitespace-nowrap select-none',
        'transition-[color,background-color,border-color,box-shadow,transform] duration-200 active:translate-y-0 active:scale-[0.98]',
        BTN_SIZES[size], BTN_VARIANTS[variant] || BTN_VARIANTS.primary,
        (disabled || loading) && 'opacity-45 cursor-not-allowed hover:translate-y-0',
        className,
      )}
    >
      {loading ? <Spinner size={iconSize} /> : Icon ? <Icon size={iconSize} strokeWidth={2.25} /> : null}
      {children}
      {IconRight && !loading && <IconRight size={iconSize} strokeWidth={2.25} />}
    </button>
  )
}

export const IconBtn = forwardRef(function IconBtn({ icon: Icon, label, onClick, className = '', badge }, ref) {
  return (
    <button ref={ref} type="button" onClick={onClick} aria-label={label} title={label}
      className={cx('relative inline-flex h-10 w-10 items-center justify-center rounded-lg text-vh-head',
        'hover:bg-vh-raised transition-colors', className)}>
      <Icon size={20} strokeWidth={2} />
      {badge ? (
        <span className="absolute right-1 top-1 h-4 min-w-[16px] rounded-full bg-vh-accent2 px-1 text-center text-[10px] font-bold leading-4 text-white">
          {badge}
        </span>
      ) : null}
    </button>
  )
})

// ── Card ──────────────────────────────────────────────────────────────────────
/**
 * tone="light": white, 2px black outline, black offset shadow (shadow={false} for flat lists)
 * tone="dark":  black panel with a mustard offset shadow; contents turn cream
 * tone="cream": cream well with no outline
 */
export function Card({
  children, className = '', onClick, selected = false, hoverable = false, as: Tag = 'div',
  tone = 'light', shadow = true,
}) {
  const interactive = hoverable || onClick
  const tones = {
    light: cx('border-2 border-vh-edge bg-vh-surface', shadow && 'shadow-hard'),
    dark: 'on-dark border-2 border-vh-night bg-vh-night shadow-accent',
    cream: 'bg-vh-raised',
  }
  return (
    <Tag
      onClick={onClick}
      className={cx(
        'rounded-2xl transition-[transform,box-shadow,background-color] duration-200',
        tones[tone] || tones.light,
        selected && tone === 'light' && 'shadow-accent',
        interactive && 'cursor-pointer text-left hover:-translate-x-0.5 hover:-translate-y-0.5',
        interactive && tone === 'light' && !selected && 'hover:shadow-hard-lg',
        className,
      )}
    >
      {children}
    </Tag>
  )
}

/** Cream label / value tile ("Signature hook · Contrarian"). */
export function Tile({ label, value, icon: Icon, className = '' }) {
  return (
    <div className={cx('rounded-xl bg-vh-raised px-4 py-3.5', className)}>
      <dt className="flex items-center gap-1.5 font-mono text-[12px] text-vh-muted">{Icon && <Icon size={12} strokeWidth={2} />}{label}</dt>
      <dd className="mt-1 text-[17px] font-semibold leading-snug text-vh-strong">{value ?? '—'}</dd>
    </div>
  )
}

// ── Badges and tags ───────────────────────────────────────────────────────────
const TONES = {
  accent: 'bg-vh-accent text-vh-ink',
  ok:     'bg-vh-text text-vh-surface',              // black chip on cream, cream chip on black
  warn:   'bg-vh-accent text-vh-ink',
  bad:    'bg-vh-accent2 text-white',
  info:   'bg-vh-accent text-vh-ink',
  cta:    'border-2 border-vh-edge text-vh-text',
  muted:  'border-2 border-vh-edge text-vh-text',
  steel:  'border-2 border-vh-edge text-vh-text',
  pop:    'bg-vh-accent2 text-white',
  dark:   'bg-vh-night text-vh-cream',
}
// Older colour names still used by data and a few screens
const TONE_ALIASES = { blurple: 'info', green: 'ok', yellow: 'warn', red: 'bad', purple: 'cta', cyan: 'info' }

export function Badge({ children, color = 'muted', size = 'sm', className = '' }) {
  const tone = TONES[TONE_ALIASES[color] || color] || TONES.muted
  const sizes = { sm: 'h-6 px-2 text-[12px]', md: 'h-7 px-2.5 text-[13px]', lg: 'h-8 px-3 text-sm' }
  return (
    <span className={cx('inline-flex items-center gap-1 rounded-md font-semibold whitespace-nowrap', tone, sizes[size], className)}>
      {children}
    </span>
  )
}

/** Red step chip "02 · SCRIPTING" (mono, uppercase). */
export function StepChip({ step, label, className = '' }) {
  return (
    <span className={cx('inline-flex h-8 items-center rounded-md bg-vh-accent2 px-3 font-mono text-[13px] font-bold uppercase tracking-[0.12em] text-white', className)}>
      {step && <>{step}<span className="mx-2">·</span></>}{label}
    </span>
  )
}

const SEG = {
  hook: 'bg-vh-hook text-vh-ink',
  setup: 'bg-vh-setup text-vh-surface',
  main: 'bg-vh-main text-white',
  evidence: 'bg-[#D6CFC4] text-vh-night',
  cta: 'border-[1.5px] border-vh-cta text-vh-cta',
}
const SEGMENT_TONE = {
  HOOK: SEG.hook, SETUP: SEG.setup, 'MAIN POINT': SEG.main, EVIDENCE: SEG.evidence, CTA: SEG.cta, CONCLUSION: SEG.cta,
  'BUILD-UP': SEG.setup, REVEAL: SEG.main, FRAMEWORK: SEG.evidence, CONFLICT: SEG.main, 'TURNING POINT': SEG.setup, LESSON: SEG.hook,
}
const BAR = {
  hook: 'bg-vh-hook', setup: 'bg-vh-setup', main: 'bg-vh-main', evidence: 'bg-vh-evidence', cta: 'border-2 border-vh-cta bg-transparent',
}
export const SEGMENT_BAR = {
  HOOK: BAR.hook, SETUP: BAR.setup, 'MAIN POINT': BAR.main, EVIDENCE: BAR.evidence, CTA: BAR.cta, CONCLUSION: BAR.cta,
  'BUILD-UP': BAR.setup, REVEAL: BAR.main, FRAMEWORK: BAR.evidence, CONFLICT: BAR.main, 'TURNING POINT': BAR.setup, LESSON: BAR.hook,
}

/** Scene segment label (HOOK, SETUP, …) in its fixed colour. */
export function SegmentTag({ segment, className = '' }) {
  return (
    <span className={cx('inline-flex h-6 items-center rounded px-2 font-mono text-[11px] font-bold uppercase tracking-[0.06em]',
      SEGMENT_TONE[segment] || SEG.cta, className)}>
      {segment}
    </span>
  )
}

// ── Scores ────────────────────────────────────────────────────────────────────
export const scoreTone = (v) => (v == null ? 'muted' : v >= 85 ? 'accent' : v >= 65 ? 'warn' : 'bad')
const BAR_FILL = { accent: 'bg-vh-accent', warn: 'bg-vh-accent', bad: 'bg-vh-accent2', muted: 'bg-transparent' }

/** Measured score 0–100; null = could not be measured (shown as —, never 0). */
export function ScoreBar({ label, value, max = 100, hint, layout = 'stacked' }) {
  const measured = value !== null && value !== undefined
  const pct = measured ? Math.min(100, Math.round((value / max) * 100)) : 0
  const tone = scoreTone(measured ? pct : null)
  const bar = (
    <div className="h-2 overflow-hidden rounded-full bg-vh-line/20">
      <motion.div className={cx('h-full rounded-full', BAR_FILL[tone])}
        initial={{ width: 0 }} whileInView={{ width: `${pct}%` }} viewport={{ once: true }}
        transition={{ duration: 0.9, ease: EASE, delay: 0.1 }} />
    </div>
  )
  if (layout === 'row') {
    return (
      <div className="flex items-center gap-3">
        <span className="w-36 shrink-0 text-sm text-vh-muted">{label}</span>
        <div className="flex-1">{bar}</div>
        <span className="w-9 text-right text-sm font-bold text-vh-strong tabular">{measured ? <CountUp value={value} /> : '—'}</span>
      </div>
    )
  }
  return (
    <div>
      <div className="mb-2.5 flex items-baseline justify-between gap-2">
        <span className="flex items-center gap-1 text-[15px] text-vh-muted">{label}{hint && <InfoTip text={hint} />}</span>
        <span className="text-[15px] font-bold leading-none text-vh-strong tabular">{measured ? <CountUp value={value} /> : '—'}</span>
      </div>
      {bar}
    </div>
  )
}

/** Small labelled number, e.g. in the action bar. */
export function Stat({ label, value, className = '' }) {
  return (
    <div className={className}>
      <p className="font-mono text-[12px] text-vh-muted">{label}</p>
      <p className="mt-0.5 text-lg font-bold leading-tight text-vh-strong tabular">{value}</p>
    </div>
  )
}

/** ⓘ with an explanation on hover / focus. */
export function InfoTip({ text, label = 'How is this measured?' }) {
  const id = useId()
  return (
    <span className="group relative inline-flex">
      <button type="button" aria-label={label} aria-describedby={id}
        className="inline-flex h-4 w-4 items-center justify-center rounded-full text-vh-muted hover:text-vh-accent focus:text-vh-accent">
        <Info size={14} strokeWidth={2.25} />
      </button>
      <span id={id} role="tooltip"
        className="pointer-events-none absolute left-1/2 top-6 z-30 w-64 -translate-x-1/2 rounded-xl border-2 border-vh-night bg-vh-night px-3 py-2
          text-xs font-normal normal-case leading-relaxed tracking-normal text-vh-cream opacity-0 shadow-accent-sm transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
        {text}
      </span>
    </span>
  )
}

// ── Job progress (long-running steps) ─────────────────────────────────────────
export function ProgressSteps({ steps, currentStep }) {
  return (
    <ol className="space-y-3">
      {steps.map((step, i) => {
        const done = i < currentStep
        const active = i === currentStep
        return (
          <li key={step.id || i} className={cx('flex items-center gap-3 text-sm')}>
            <span className={cx('flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2',
              done ? 'border-vh-night bg-vh-night text-vh-cream' : active ? 'border-vh-night bg-vh-accent text-vh-ink' : 'border-vh-edge')}>
              {done ? <Check size={13} strokeWidth={3} /> : active ? <Spinner size={12} /> : null}
            </span>
            <span className={active ? 'font-semibold text-vh-strong' : 'text-vh-text'}>{step.label}</span>
          </li>
        )
      })}
    </ol>
  )
}

export function Spinner({ size = 16, className = '' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" className={cx('animate-spin', className)} style={{ minWidth: size }} aria-hidden="true">
      <circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" strokeOpacity=".25" strokeWidth="2.5" />
      <path d="M8 2 A6 6 0 0 1 14 8" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  )
}

// ── Page layout ───────────────────────────────────────────────────────────────

/**
 * A page: page-specific line art down both sides and a themed band along the
 * bottom (art = key of components/art DECOR), then the content column.
 */
export function Page({ children, className = '', art, width = 'max-w-page' }) {
  return (
    <div className="relative isolate flex min-h-[60vh] flex-1 flex-col overflow-hidden">
      {art && <PageDecor kind={art} />}
      <div className={cx('relative mx-auto w-full px-4 pb-48 pt-10 sm:px-8 sm:pt-12', width, className)}>
        {children}
      </div>
    </div>
  )
}

/**
 * Page title as in the design references: red step chip + topic chip, a huge
 * Bebas title whose second part sits in a mustard box, the lead on the right.
 * title: 'Text' or ['Plain part', 'Highlighted part'].
 */
export function PageHero({ step, label, title, lead, aside, topic }) {
  const [plain, highlight] = Array.isArray(title) ? title : [title]
  return (
    <Stagger as="header" gap={0.07} className="mb-9 grid gap-x-10 gap-y-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,17rem)] lg:items-end">
      <div className="min-w-0">
        {(step || label || topic) && (
          <StaggerItem className="relative z-10 flex flex-wrap items-center gap-2.5">
            {(step || label) && <StepChip step={step} label={label} />}
            {topic && <TopicPill topic={topic} />}
          </StaggerItem>
        )}
        <h1 className="mt-3">
          <StaggerItem as="span" className="display heading-glow inline text-[clamp(3.2rem,8vw,6.1rem)] leading-[1.02]">
            {plain}{highlight && ' '}
            {highlight && (
              <span className="box-decoration-clone inline rounded-md bg-vh-accent px-[0.12em] pb-[0.06em] pt-[0.16em] text-vh-ink">
                {highlight}
              </span>
            )}
          </StaggerItem>
        </h1>
      </div>
      {(lead || aside) && (
        <StaggerItem className="space-y-4 lg:pb-3">
          {lead && <p className="text-[16px] leading-relaxed text-vh-text">{lead}</p>}
          {aside}
        </StaggerItem>
      )}
    </Stagger>
  )
}

function TopicPill({ topic }) {
  return (
    <span className="inline-flex h-8 max-w-[min(26rem,100%)] items-center rounded-md border-2 border-vh-edge bg-vh-bg px-3 font-mono text-[13px] text-vh-strong">
      <span className="truncate">Topic: {topic}</span>
    </span>
  )
}

/**
 * Checklist as pills ("✓ 5 scenes in order").
 * items: [{ label, state: 'ok' | 'warn' | 'off' }]
 */
export function Checklist({ title, items }) {
  return (
    <div>
      {title && <p className="mb-2.5 text-sm font-semibold text-vh-head">{title}</p>}
      <ul className="flex flex-wrap gap-2">
        {items.map(({ label, state = 'ok' }) => (
          <li key={label} className={cx('inline-flex items-center gap-1.5 rounded-full border-2 px-3 py-1 text-[13px] font-semibold',
            state === 'warn' ? 'border-vh-accent bg-vh-accent text-vh-ink' : 'border-vh-edge text-vh-text', state === 'off' && 'border-dashed')}>
            {state === 'ok' ? <Check size={14} strokeWidth={3} />
              : state === 'warn' ? <AlertTriangle size={13} strokeWidth={2.5} /> : <Circle size={12} strokeWidth={2.5} />}
            {label}
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Black bar at the end of a page: summary on the left, the page's actions on the right. */
export function ActionBar({ children, actions }) {
  return (
    <div className="on-dark mt-10 flex flex-wrap items-center justify-between gap-x-8 gap-y-4 rounded-2xl bg-vh-night px-5 py-5 sm:px-7">
      <div className="flex min-w-0 flex-wrap items-center gap-x-9 gap-y-3">{children}</div>
      <div className="flex w-full flex-wrap items-center gap-3 sm:w-auto [&>*]:flex-1 sm:[&>*]:flex-none">{actions}</div>
    </div>
  )
}

/** Section title inside a page (Bebas, as "RECENT CONTENT"). */
export function SectionTitle({ children, right, className = '' }) {
  return (
    <div className={cx('mb-4 flex items-end justify-between gap-3', className)}>
      <h2 className="display text-[clamp(1.9rem,3.4vw,2.6rem)] text-vh-head">{children}</h2>
      {right}
    </div>
  )
}

/** Kept for screens that still use an icon + title header. */
export function SectionHeader({ title, subtitle }) {
  return (
    <div className="mb-6">
      <h2 className="display text-3xl text-vh-head">{title}</h2>
      {subtitle && <p className="mt-1 text-sm text-vh-muted">{subtitle}</p>}
    </div>
  )
}

export function EmptyState({ icon: Icon, title, children, action }) {
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center">
      {Icon && (
        <span className="mb-4 flex h-14 w-14 items-center justify-center rounded-xl border-2 border-dashed border-vh-edge text-vh-head">
          <Icon size={24} strokeWidth={2} />
        </span>
      )}
      <p className="display text-2xl text-vh-strong">{title}</p>
      {children && <p className="mt-1 max-w-sm text-sm text-vh-text">{children}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

export function Center({ children, className = '' }) {
  return <div className={cx('flex h-full w-full flex-col items-center justify-center', className)}>{children}</div>
}

// ── Forms ─────────────────────────────────────────────────────────────────────
const FIELD = 'w-full rounded-xl border-2 bg-vh-input px-4 text-[15px] text-vh-strong placeholder:text-vh-text/45 ' +
  'transition-colors focus:outline-none focus:ring-4 focus:ring-vh-accent/40 disabled:opacity-60'

export function Field({ label, error, hint, htmlFor, children }) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && <label htmlFor={htmlFor} className="font-mono text-[12px] font-semibold uppercase tracking-[0.08em] text-vh-muted">{label}</label>}
      {children}
      {error ? <p className="text-xs font-semibold text-vh-bad">{error}</p> : hint ? <p className="font-mono text-xs text-vh-faint">{hint}</p> : null}
    </div>
  )
}

export function Input({ label, error, hint, className = '', id, ...props }) {
  const auto = useId()
  const fid = id || auto
  return (
    <Field label={label} error={error} hint={hint} htmlFor={fid}>
      <input id={fid} className={cx(FIELD, 'h-12', error ? 'border-vh-bad' : 'border-vh-edge', className)} {...props} />
    </Field>
  )
}

export function Textarea({ label, error, hint, className = '', id, ...props }) {
  const auto = useId()
  const fid = id || auto
  return (
    <Field label={label} error={error} hint={hint} htmlFor={fid}>
      <textarea id={fid} className={cx(FIELD, 'resize-y py-3.5 leading-relaxed', error ? 'border-vh-bad' : 'border-vh-edge', className)} {...props} />
    </Field>
  )
}

export function Select({ label, error, options = [], className = '', id, ...props }) {
  const auto = useId()
  const fid = id || auto
  return (
    <Field label={label} error={error} htmlFor={fid}>
      <select id={fid} className={cx(FIELD, 'h-12 cursor-pointer', error ? 'border-vh-bad' : 'border-vh-edge', className)} {...props}>
        {options.map((o) => <option key={o.value ?? o} value={o.value ?? o}>{o.label ?? o}</option>)}
      </select>
    </Field>
  )
}

// ── Feedback ──────────────────────────────────────────────────────────────────
const ALERTS = {
  info:    { cls: 'border-dashed border-vh-edge', chip: 'Note', chipCls: 'bg-vh-text text-vh-surface', icon: Info },
  success: { cls: 'border-vh-edge bg-vh-surface', chip: 'Done', chipCls: 'bg-vh-text text-vh-surface', icon: CircleCheck },
  warning: { cls: 'border-vh-accent bg-vh-accent/15', chip: 'Heads up', chipCls: 'bg-vh-accent text-vh-ink', icon: AlertTriangle },
  error:   { cls: 'border-vh-accent2 bg-vh-accent2/[0.06]', chip: 'Error', chipCls: 'bg-vh-accent2 text-white', icon: AlertTriangle },
}

/** Notice box like the design's "PREVIEW · Instagram publishing is not connected yet". */
export function Alert({ type = 'info', children, className = '', chip }) {
  const a = ALERTS[type] || ALERTS.info
  return (
    <div role={type === 'error' ? 'alert' : 'status'} className={cx('flex items-start gap-3 rounded-xl border-2 px-4 py-3', a.cls, className)}>
      <span className={cx('mt-px inline-flex h-6 shrink-0 items-center rounded px-2 font-mono text-[11px] font-bold uppercase tracking-[0.08em]', a.chipCls)}>
        {chip || a.chip}
      </span>
      <div className="min-w-0 pt-0.5 text-sm font-medium leading-relaxed text-vh-text">{children}</div>
    </div>
  )
}

export function Modal({ open, onClose, title, children, width = 'max-w-lg' }) {
  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => e.key === 'Escape' && onClose?.()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])
  return createPortal(
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label={title}>
          <motion.div className="absolute inset-0 bg-vh-night/60" onClick={onClose}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }} />
          <motion.div className={cx('relative max-h-[90dvh] w-full overflow-y-auto rounded-2xl border-2 border-vh-night bg-white shadow-accent', width)}
            initial={{ opacity: 0, y: 16, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.98 }} transition={{ duration: 0.28, ease: EASE }}>
            <div className="flex items-center justify-between border-b-2 border-vh-night px-6 py-4">
              <h3 className="display text-[1.9rem] text-vh-head">{title}</h3>
              <IconBtn icon={X} label="Close" onClick={onClose} className="-mr-2 h-9 w-9" />
            </div>
            <div className="px-6 py-5">{children}</div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  )
}

export function Divider({ label }) {
  return (
    <div className="my-5 flex items-center gap-3">
      <div className="h-0.5 flex-1 bg-vh-line/20" />
      {label && <span className="font-mono text-xs text-vh-faint">{label}</span>}
      <div className="h-0.5 flex-1 bg-vh-line/20" />
    </div>
  )
}

/** Toggle group, as the design's "Publish now | Schedule". */
export function Segmented({ options, value, onChange, label, size = 'md' }) {
  const h = size === 'sm' ? 'h-9 px-3 text-[13px]' : 'h-11 px-5 text-[15px]'
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex max-w-full overflow-x-auto rounded-xl border-2 border-vh-edge bg-vh-surface">
      {options.map((o) => (
        <button key={o.value} type="button" role="radio" aria-checked={value === o.value} onClick={() => onChange(o.value)}
          className={cx('shrink-0 whitespace-nowrap font-semibold transition-colors first:rounded-l-[10px] last:rounded-r-[10px]', h,
            value === o.value ? 'bg-vh-text text-vh-surface' : 'text-vh-text hover:bg-vh-raised')}>
          {o.label}
        </button>
      ))}
    </div>
  )
}

/** Remembers a boolean in component state; small helper for disclosure toggles. */
export function useToggle(initial = false) {
  const [on, setOn] = useState(initial)
  return [on, () => setOn((v) => !v), setOn]
}
