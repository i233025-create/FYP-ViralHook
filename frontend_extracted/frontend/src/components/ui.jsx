// ─────────────────────────────────────────────────────────────────────────────
// VIRALHOOK — SHARED UI COMPONENTS
// ─────────────────────────────────────────────────────────────────────────────
import { CheckCircle, X, AlertTriangle, Info } from 'lucide-react'

// ── Button ────────────────────────────────────────────────────────────────────
export function Btn({
  children, onClick, variant = 'primary', size = 'md',
  disabled = false, loading = false, className = '', type = 'button', icon: Icon,
}) {
  const base = 'inline-flex items-center justify-center gap-2 font-semibold rounded-lg transition-all duration-150 select-none focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-discord-dark'
  const sizes = {
    sm:  'px-3 py-1.5 text-xs',
    md:  'px-4 py-2.5 text-sm',
    lg:  'px-6 py-3.5 text-base',
    xl:  'px-8 py-4 text-lg',
  }
  const variants = {
    primary:   'bg-discord-blurple hover:bg-discord-blurple_hover text-white focus:ring-discord-blurple shadow-lg hover:shadow-discord-blurple/25 hover:-translate-y-px',
    secondary: 'bg-discord-sidebar hover:bg-discord-hover text-discord-text border border-discord-faint/40 hover:border-discord-faint/70 focus:ring-discord-faint',
    ghost:     'bg-transparent hover:bg-discord-hover text-discord-muted hover:text-discord-white focus:ring-discord-faint',
    danger:    'bg-discord-red/15 hover:bg-discord-red text-discord-red hover:text-white border border-discord-red/40 focus:ring-discord-red',
    success:   'bg-discord-green/15 hover:bg-discord-green text-discord-green hover:text-white border border-discord-green/40 focus:ring-discord-green',
    outline:   'bg-transparent border border-discord-blurple text-discord-blurple hover:bg-discord-blurple hover:text-white focus:ring-discord-blurple',
  }
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={`${base} ${sizes[size]} ${variants[variant]} ${disabled || loading ? 'opacity-50 cursor-not-allowed !translate-y-0' : ''} ${className}`}
    >
      {loading ? <Spinner size={size === 'sm' ? 12 : 16} /> : Icon ? <Icon size={size === 'sm' ? 12 : 16} /> : null}
      {children}
    </button>
  )
}

// ── Card ──────────────────────────────────────────────────────────────────────
export function Card({ children, className = '', onClick, selected = false, hoverable = false }) {
  const base = 'bg-discord-sidebar border rounded-xl transition-all duration-200'
  const border = selected
    ? 'border-discord-blurple ring-2 ring-discord-blurple/40'
    : 'border-discord-faint/25'
  const hover = (hoverable || onClick)
    ? 'hover:border-discord-faint/60 cursor-pointer hover:-translate-y-0.5 hover:shadow-lg'
    : ''
  return (
    <div onClick={onClick} className={`${base} ${border} ${hover} ${className}`}>
      {children}
    </div>
  )
}

// ── Badge ─────────────────────────────────────────────────────────────────────
export function Badge({ children, color = 'blurple', size = 'sm' }) {
  const colors = {
    blurple: 'bg-discord-blurple/20 text-discord-blurple border-discord-blurple/35',
    green:   'bg-discord-green/20 text-discord-green border-discord-green/35',
    yellow:  'bg-discord-yellow/20 text-discord-yellow border-discord-yellow/35',
    red:     'bg-discord-red/20 text-discord-red border-discord-red/35',
    purple:  'bg-purple-500/20 text-purple-400 border-purple-500/35',
    cyan:    'bg-cyan-500/20 text-cyan-400 border-cyan-500/35',
    muted:   'bg-discord-faint/30 text-discord-muted border-discord-faint/40',
  }
  const sizes = { sm: 'px-2 py-0.5 text-xs', md: 'px-2.5 py-1 text-xs', lg: 'px-3 py-1 text-sm' }
  return (
    <span className={`inline-flex items-center font-semibold rounded-full border ${colors[color]} ${sizes[size]}`}>
      {children}
    </span>
  )
}

// ── Score bar ─────────────────────────────────────────────────────────────────
export function ScoreBar({ label, value, max = 100 }) {
  const pct = Math.min(100, Math.round((value / max) * 100))
  const color = pct >= 85 ? 'bg-discord-green' : pct >= 65 ? 'bg-discord-yellow' : 'bg-discord-red'
  return (
    <div className="flex items-center gap-3">
      <span className="text-discord-muted text-xs w-36 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-discord-faint/30 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-500 ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-discord-white text-xs font-bold w-8 text-right">{value}%</span>
    </div>
  )
}

// ── Progress Steps ────────────────────────────────────────────────────────────
export function ProgressSteps({ steps, currentStep }) {
  return (
    <div className="space-y-2">
      {steps.map((step, i) => {
        const done    = i < currentStep
        const active  = i === currentStep
        const pending = i > currentStep
        return (
          <div key={step.id || i} className={`flex items-center gap-3 text-sm transition-all duration-300 ${pending ? 'opacity-40' : ''}`}>
            <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0
              ${done ? 'bg-discord-green' : active ? 'bg-discord-blurple' : 'bg-discord-faint/40'}`}>
              {done
                ? <CheckCircle size={12} className="text-white" />
                : active
                  ? <Spinner size={10} light />
                  : <span className="w-1.5 h-1.5 rounded-full bg-discord-muted" />}
            </div>
            <span className={done ? 'text-discord-green' : active ? 'text-discord-white font-medium' : 'text-discord-muted'}>
              {step.label}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// ── Spinner ───────────────────────────────────────────────────────────────────
export function Spinner({ size = 16, light = false }) {
  return (
    <svg
      width={size} height={size} viewBox="0 0 16 16"
      className="animate-spin"
      style={{ minWidth: size }}
    >
      <circle cx="8" cy="8" r="6" fill="none"
        stroke={light ? 'rgba(255,255,255,0.3)' : 'rgba(88,101,242,0.3)'} strokeWidth="2" />
      <path d="M8 2 A6 6 0 0 1 14 8" fill="none"
        stroke={light ? 'white' : '#5865F2'} strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}

// ── Loading Dots ──────────────────────────────────────────────────────────────
export function LoadingDots({ label }) {
  return (
    <div className="flex flex-col items-center gap-4 py-10">
      <div className="flex gap-1.5">
        {[0, 1, 2].map(i => (
          <span key={i} className="w-2 h-2 rounded-full bg-discord-blurple animate-bounce"
            style={{ animationDelay: `${i * 0.15}s`, animationDuration: '0.8s' }} />
        ))}
      </div>
      {label && <p className="text-discord-muted text-sm">{label}</p>}
    </div>
  )
}

// ── Section header ────────────────────────────────────────────────────────────
export function SectionHeader({ title, subtitle, icon: Icon }) {
  return (
    <div className="mb-6">
      {Icon && <div className="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-discord-blurple/15 mb-3"><Icon size={20} className="text-discord-blurple" /></div>}
      <h2 className="text-discord-white font-bold text-xl">{title}</h2>
      {subtitle && <p className="text-discord-muted text-sm mt-1">{subtitle}</p>}
    </div>
  )
}

// ── Page wrapper ──────────────────────────────────────────────────────────────
export function Page({ children, className = '' }) {
  return (
    <div className={`flex-1 overflow-y-auto p-6 md:p-8 animate-fadeIn ${className}`}>
      {children}
    </div>
  )
}

// ── Center wrapper ─────────────────────────────────────────────────────────────
export function Center({ children, className = '' }) {
  return (
    <div className={`flex flex-col items-center justify-center h-full w-full ${className}`}>
      {children}
    </div>
  )
}

// ── Input ─────────────────────────────────────────────────────────────────────
export function Input({ label, error, className = '', ...props }) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && <label className="text-discord-muted text-xs font-semibold uppercase tracking-wide">{label}</label>}
      <input
        className={`w-full bg-discord-input border ${error ? 'border-discord-red/60' : 'border-discord-faint/40'} 
          rounded-lg px-3.5 py-2.5 text-discord-white text-sm placeholder-discord-muted/60
          focus:outline-none focus:border-discord-blurple focus:ring-1 focus:ring-discord-blurple
          transition-colors ${className}`}
        {...props}
      />
      {error && <p className="text-discord-red text-xs">{error}</p>}
    </div>
  )
}

// ── Textarea ──────────────────────────────────────────────────────────────────
export function Textarea({ label, error, className = '', ...props }) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && <label className="text-discord-muted text-xs font-semibold uppercase tracking-wide">{label}</label>}
      <textarea
        className={`w-full bg-discord-input border ${error ? 'border-discord-red/60' : 'border-discord-faint/40'}
          rounded-lg px-3.5 py-2.5 text-discord-white text-sm placeholder-discord-muted/60
          focus:outline-none focus:border-discord-blurple focus:ring-1 focus:ring-discord-blurple
          transition-colors resize-none ${className}`}
        {...props}
      />
      {error && <p className="text-discord-red text-xs">{error}</p>}
    </div>
  )
}

// ── Select ────────────────────────────────────────────────────────────────────
export function Select({ label, error, options = [], className = '', ...props }) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && <label className="text-discord-muted text-xs font-semibold uppercase tracking-wide">{label}</label>}
      <select
        className={`w-full bg-discord-input border ${error ? 'border-discord-red/60' : 'border-discord-faint/40'}
          rounded-lg px-3.5 py-2.5 text-discord-white text-sm
          focus:outline-none focus:border-discord-blurple focus:ring-1 focus:ring-discord-blurple
          transition-colors cursor-pointer ${className}`}
        {...props}
      >
        {options.map((o) => (
          <option key={o.value ?? o} value={o.value ?? o} className="bg-discord-darker">
            {o.label ?? o}
          </option>
        ))}
      </select>
      {error && <p className="text-discord-red text-xs">{error}</p>}
    </div>
  )
}

// ── Modal ─────────────────────────────────────────────────────────────────────
export function Modal({ open, onClose, title, children, width = 'max-w-lg' }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        className={`relative w-full ${width} bg-discord-sidebar border border-discord-faint/30 rounded-2xl shadow-2xl animate-slideUp`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-discord-faint/20">
          <h3 className="text-discord-white font-bold text-base">{title}</h3>
          <button onClick={onClose} className="text-discord-muted hover:text-discord-white transition-colors p-1 rounded">
            <X size={18} />
          </button>
        </div>
        <div className="px-6 py-5">{children}</div>
      </div>
    </div>
  )
}

// ── Alert ─────────────────────────────────────────────────────────────────────
export function Alert({ type = 'info', children }) {
  const styles = {
    info:    { bg: 'bg-discord-blurple/10 border-discord-blurple/30 text-discord-blurple', Icon: Info },
    success: { bg: 'bg-discord-green/10 border-discord-green/30 text-discord-green', Icon: CheckCircle },
    warning: { bg: 'bg-discord-yellow/10 border-discord-yellow/30 text-discord-yellow', Icon: AlertTriangle },
    error:   { bg: 'bg-discord-red/10 border-discord-red/30 text-discord-red', Icon: AlertTriangle },
  }
  const { bg, Icon } = styles[type] || styles.info
  return (
    <div className={`flex items-start gap-3 px-4 py-3 rounded-lg border ${bg}`}>
      <Icon size={16} className="flex-shrink-0 mt-0.5" />
      <div className="text-sm leading-relaxed">{children}</div>
    </div>
  )
}

// ── Divider ───────────────────────────────────────────────────────────────────
export function Divider({ label }) {
  return (
    <div className="flex items-center gap-3 my-4">
      <div className="flex-1 h-px bg-discord-faint/30" />
      {label && <span className="text-discord-faint text-xs font-medium">{label}</span>}
      <div className="flex-1 h-px bg-discord-faint/30" />
    </div>
  )
}

// ── Step pill ─────────────────────────────────────────────────────────────────
export function StepPill({ number, label, active = false, done = false }) {
  return (
    <div className={`flex items-center gap-2 text-xs font-semibold transition-colors ${done ? 'text-discord-green' : active ? 'text-discord-white' : 'text-discord-faint'}`}>
      <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold
        ${done ? 'bg-discord-green text-white' : active ? 'bg-discord-blurple text-white' : 'bg-discord-faint/30 text-discord-faint'}`}>
        {done ? '✓' : number}
      </span>
      {label}
    </div>
  )
}
