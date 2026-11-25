// ─────────────────────────────────────────────────────────────────────────────
// Option cards ("OPTION 01 · A FEW SECONDS") and the small "what you get"
// pictures inside them, built from UI shapes in the theme colours.
// Cards alternate white / black like the design's "Choose a path".
// All previews are decorative: aria-hidden.
// ─────────────────────────────────────────────────────────────────────────────
import { ArrowRight, Film, Instagram, Play, Search, TrendingUp, Upload } from 'lucide-react'
import { SEGMENT_BAR } from './ui'
import { Stagger, StaggerItem } from './motion'

const SEGS = ['HOOK', 'SETUP', 'MAIN POINT', 'EVIDENCE', 'CONCLUSION']
const cx = (...c) => c.filter(Boolean).join(' ')

/**
 * A choice card: kicker, Bebas title + one line, preview, a 2×2 spec grid,
 * and "Best for" with the call to action.
 * specs: [{ icon, label, value }] · tone: 'light' | 'dark' (OptionGrid alternates)
 */
export function OptionCard({
  number, kicker, title, line, specs = [], bestFor, preview, badge, cta = 'Choose', onClick, disabled, tone = 'light',
}) {
  const dark = tone === 'dark'
  return (
    <button type="button" onClick={onClick} disabled={disabled}
      className={cx('group flex w-full flex-col rounded-2xl border-2 p-6 text-left transition-[transform,box-shadow] duration-200 sm:p-8',
        dark ? 'on-dark border-vh-night bg-vh-night shadow-accent enabled:hover:shadow-[10px_10px_0_0_rgb(var(--vh-accent))]'
          : 'border-vh-night bg-white shadow-hard enabled:hover:shadow-hard-lg',
        'enabled:hover:-translate-x-0.5 enabled:hover:-translate-y-0.5 disabled:cursor-not-allowed')}>
      <div className="flex min-h-[1.75rem] items-center justify-between gap-3">
        <span className={cx('font-mono text-[13px] font-bold uppercase tracking-[0.1em]', dark ? 'text-vh-accent' : 'text-vh-accent2')}>
          Option {number}{kicker && <> · {kicker}</>}
        </span>
        {badge}
      </div>
      <h2 className="display mt-4 text-[clamp(2.3rem,3.6vw,3.2rem)] text-vh-head">{title}</h2>
      <p className="mt-3 text-[16px] leading-relaxed text-vh-text">{line}</p>

      {preview && (
        <div className={cx('relative mt-6 h-36 overflow-hidden rounded-xl',
          dark ? 'bg-vh-raised' : 'border-2 border-vh-night bg-vh-raised', disabled && 'grayscale')}>
          {preview}
        </div>
      )}

      {specs.length > 0 && (
        <dl className="mt-5 grid grid-cols-2 gap-3">
          {specs.map(({ label, value }) => (
            <div key={label} className="rounded-xl bg-vh-raised px-4 py-3">
              <dt className="font-mono text-[12px] text-vh-muted">{label}</dt>
              <dd className="mt-1 text-[15px] font-bold leading-snug text-vh-strong">{value}</dd>
            </div>
          ))}
        </dl>
      )}

      <div className="flex-1" />
      <div className="mt-7 flex items-center justify-between gap-4">
        {bestFor && <p className="min-w-0 text-[15px] text-vh-text">Best for {bestFor.charAt(0).toLowerCase() + bestFor.slice(1)}</p>}
        {!disabled && (
          <span className={cx('inline-flex h-12 shrink-0 items-center gap-2 rounded-xl border-2 px-5 text-[16px] font-bold transition-transform group-hover:translate-x-0.5',
            dark ? 'border-vh-cream bg-vh-cream text-vh-night' : 'border-vh-night bg-vh-accent text-vh-ink')}>
            {cta} <ArrowRight size={17} strokeWidth={2.5} />
          </span>
        )}
      </div>
    </button>
  )
}

/** Grid of OptionCards that appear one after another; every second card is black. */
export function OptionGrid({ cols = 2, children }) {
  const grid = cols === 3 ? 'md:grid-cols-2 lg:grid-cols-3' : 'md:grid-cols-2'
  const kids = [].concat(children).filter(Boolean)
  return (
    <Stagger className={`grid gap-7 ${grid}`}>
      {kids.map((child, i) => (
        <StaggerItem key={i} className="grid">
          {child.props.tone ? child : { ...child, props: { ...child.props, tone: i % 2 ? 'dark' : 'light' } }}
        </StaggerItem>
      ))}
    </Stagger>
  )
}

// ── Previews ─────────────────────────────────────────────────────────────────

/** Mini editor timeline: caption track, clips in segment colours, ruler ticks. */
export function TimelinePreview({ scenes = [] }) {
  const segs = scenes.length ? scenes.map((s) => s.segment) : SEGS
  return (
    <div className="absolute inset-0 flex flex-col justify-center gap-3 px-5" aria-hidden="true">
      <div className="flex gap-1.5">
        {[22, 30, 26].map((w, i) => <span key={i} className="h-2.5 rounded-sm bg-vh-text/20" style={{ width: `${w}%` }} />)}
      </div>
      <div className="flex h-9 gap-1.5">
        {segs.map((seg, i) => (
          <span key={i} className={cx('rounded-sm', SEGMENT_BAR[seg] || SEGMENT_BAR.CONCLUSION)} style={{ flexGrow: [3, 5, 7, 7, 5][i % 5], flexBasis: 0 }} />
        ))}
      </div>
      <div className="flex justify-between">
        {Array.from({ length: 34 }, (_, i) => <span key={i} className="h-2.5 w-0.5 bg-vh-text" />)}
      </div>
    </div>
  )
}

/** Three 9:16 frames; the middle one is mustard with a play button. */
export function PhonePreview({ scenes = [] }) {
  const caption = scenes[0]?.caption
  return (
    <div className="absolute inset-0 flex items-center justify-center gap-4" aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <div key={i}
          className={cx('relative flex h-[5.4rem] w-[3.3rem] items-center justify-center rounded-lg',
            i === 1 ? 'bg-vh-accent' : 'border-2 border-vh-line/60')}
          style={{ transform: i === 1 ? 'none' : `rotate(${i === 0 ? -5 : 5}deg)` }}>
          {i === 1 && <Play size={18} className="ml-0.5 text-vh-night" fill="currentColor" />}
          {i === 1 && caption && (
            <span className="absolute inset-x-1 bottom-1.5 truncate rounded-sm bg-vh-night px-0.5 text-center text-[6px] font-bold uppercase text-vh-cream">{caption}</span>
          )}
        </div>
      ))}
    </div>
  )
}

/** Instagram profile grid of reels being imported. */
export function ReelGridPreview() {
  return (
    <div className="absolute inset-0 flex items-center justify-center gap-5" aria-hidden="true">
      <div className="grid grid-cols-3 gap-1.5">
        {Array.from({ length: 6 }, (_, i) => (
          <span key={i} className={cx('flex h-[3.1rem] w-9 items-center justify-center rounded',
            i === 1 ? 'bg-vh-accent' : 'border-2 border-vh-line/40')}>
            <Play size={10} className="text-vh-text" fill="currentColor" />
          </span>
        ))}
      </div>
      <ArrowRight size={20} className="text-vh-text" strokeWidth={2.5} />
      <span className="flex h-12 w-12 items-center justify-center rounded-xl border-2 border-vh-line text-vh-text"><Instagram size={22} /></span>
    </div>
  )
}

/** A drop zone with a few video files landing in it. */
export function UploadPreview() {
  const files = ['kulfi_review.mp4', 'chapli_kabab.mp4', 'street_food.mp4']
  return (
    <div className="absolute inset-0 flex items-center justify-center px-5" aria-hidden="true">
      <div className="w-full max-w-[16rem] rounded-xl border-2 border-dashed border-vh-line/70 p-2.5">
        <div className="mb-1.5 flex items-center justify-center gap-1.5 font-mono text-[10px] font-semibold"><Upload size={12} /> Drop videos</div>
        <div className="space-y-1.5">
          {files.map((f, i) => (
            <div key={f} className="flex items-center gap-2 rounded-md bg-vh-surface px-2 py-1">
              <Film size={11} className="shrink-0" />
              <span className="flex-1 truncate font-mono text-[10px]">{f}</span>
              <span className="h-1.5 w-10 overflow-hidden rounded-full bg-vh-text/15">
                <span className="block h-full rounded-full bg-vh-accent" style={{ width: `${[100, 70, 35][i]}%` }} />
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

/** Niche chips: starting from preferences, no videos needed. */
export function NichePreview() {
  const chips = ['Food', 'Tech', 'Beauty', 'Fitness', 'Finance', 'Education']
  return (
    <div className="absolute inset-0 flex items-center justify-center px-6" aria-hidden="true">
      <div className="flex max-w-[16rem] flex-wrap justify-center gap-1.5">
        {chips.map((c, i) => (
          <span key={c} className={cx('rounded-full border-2 px-2.5 py-0.5 text-[12px] font-semibold',
            i === 0 ? 'border-vh-night bg-vh-accent text-vh-ink' : 'border-vh-line/60 text-vh-text')}>{c}</span>
        ))}
      </div>
    </div>
  )
}

/** A text box with your idea being typed. */
export function IdeaInputPreview() {
  return (
    <div className="absolute inset-0 flex items-center justify-center px-5" aria-hidden="true">
      <div className="w-full max-w-[17rem] rounded-lg border-2 border-vh-line bg-vh-surface p-2.5">
        <p className="font-mono text-[10px] font-semibold uppercase">Your idea</p>
        <p className="mt-1 text-[12px] font-medium leading-snug text-vh-text">
          Rs 50 vs Rs 500 kulfi — is the expensive one worth it?<span className="ml-0.5 inline-block h-3 w-0.5 translate-y-0.5 animate-pulse bg-vh-accent" />
        </p>
        <div className="mt-2 flex justify-end"><span className="rounded bg-vh-accent px-2 py-0.5 text-[10px] font-bold text-vh-ink">Continue</span></div>
      </div>
    </div>
  )
}

/** A ranked list of trending topics with scores. */
export function TrendListPreview() {
  const rows = [['Street food under Rs 100', 92], ['Oldest shops in Lahore', 84], ['Rating every kulfi', 77]]
  return (
    <div className="absolute inset-0 flex items-center justify-center px-5" aria-hidden="true">
      <div className="w-full max-w-[17rem] space-y-1.5">
        <div className="mb-1 flex items-center gap-1.5 font-mono text-[10px] font-semibold"><Search size={11} /> Last 14 days · YouTube Shorts</div>
        {rows.map(([t, v], i) => (
          <div key={t} className="flex items-center gap-2 rounded-md bg-vh-surface px-2 py-1">
            <span className="w-4 font-mono text-[10px] font-bold text-vh-accent2">0{i + 1}</span>
            <span className="flex-1 truncate text-[11px] font-medium">{t}</span>
            <TrendingUp size={11} className={i === 0 ? 'text-vh-accent' : ''} />
            <span className="w-5 text-right text-[11px] font-bold">{v}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
