import { useEffect, useRef, useState } from 'react'
import {
  Menu, X, Check, Lock, LayoutDashboard, FolderOpen, CalendarClock, Settings, LogOut, CreditCard, Sparkles,
} from 'lucide-react'
import { useApp } from '../context/AppContext'
import { resendVerification } from '../services/api'
import Logo from './brand/Logo'
import { IconBtn } from './ui'
import { AnimatePresence, EASE, motion } from './motion'
import PaywallModal from './PaywallModal'
import { WORKFLOW, workflowState } from './shell/workflow'

const cx = (...c) => c.filter(Boolean).join(' ')

// Screens drawn without the app chrome (they have their own full-screen layout)
const BARE = ['boot', 'landing', 'auth', 'auth-signup', 'verify-email', 'reset-password', 'checkout-demo']
// Onboarding: header with logo + account only (no workflow yet)
const ONBOARDING = ['creator-type', 'onboarding-new', 'onboarding-experienced']

export default function AppShell({ children }) {
  const app = useApp()
  const { screen, user } = app
  // ?drawer=1 opens the menu on load (development preview only)
  const [drawerOpen, setDrawerOpen] = useState(
    import.meta.env.DEV && new URLSearchParams(window.location.search).has('drawer'))
  const firstScreen = useRef(screen)

  useEffect(() => { if (screen !== firstScreen.current) setDrawerOpen(false) }, [screen])

  // signed-out visitors see pricing with the public header (rendered by the page itself)
  if (BARE.includes(screen) || (!user && screen === 'pricing')) return <>{children}</>
  const onboarding = ONBOARDING.includes(screen)
  const steps = workflowState(screen, app)

  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-vh-accent focus:px-3 focus:py-2 focus:text-vh-ink">
        Skip to content
      </a>
      <header className="on-dark relative z-40 bg-vh-night">
        <div className="mx-auto flex h-[4.5rem] max-w-[90rem] items-center gap-2 px-3 sm:px-8">
          {!onboarding && <IconBtn icon={Menu} label="Open menu" onClick={() => setDrawerOpen(true)} className="-ml-1 hover:bg-vh-frame" />}
          <button type="button" onClick={() => app.creatorProfile && app.navigate('dashboard')}
            className="mr-2 rounded-md px-1 py-1" aria-label="ViralHook home">
            <Logo />
          </button>
          <div className="ml-auto flex items-center gap-2 sm:gap-4">
            <PlanPill billing={app.billing} navigate={app.navigate} />
            {!onboarding && app.creatorProfile && (
              <button type="button" onClick={() => app.navigate('dashboard')}
                className={cx('hidden text-[15px] font-semibold text-vh-cream underline-offset-4 hover:underline sm:block', screen === 'dashboard' && 'underline')}>
                Studio
              </button>
            )}
            <UserMenu user={user} onLogout={app.logout} navigate={app.navigate} />
          </div>
        </div>
        {!onboarding && <FilmStrip steps={steps} navigate={app.navigate} />}
      </header>

      {user && user.emailVerified === false && <VerifyBanner email={user.email} />}

      <main id="main" className="relative flex flex-1 flex-col">{children}</main>
      <PaywallModal />

      <AnimatePresence>
        {!onboarding && drawerOpen && (
          <NavDrawer key="drawer" onClose={() => setDrawerOpen(false)} steps={steps} app={app} />
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Workflow progress: a film strip of the five steps ─────────────────────────

function FilmStrip({ steps, navigate }) {
  return (
    <nav aria-label="Video workflow" className="mx-auto max-w-[90rem] px-3 pb-4 sm:px-8">
      <div className="sprockets" aria-hidden="true" />
      <ol className="my-3 grid grid-cols-5 gap-1.5 sm:my-4 sm:gap-3">
        {steps.map((s) => <li key={s.key} className="min-w-0"><Frame step={s} onClick={() => s.unlocked && navigate(s.target)} /></li>)}
      </ol>
      <div className="sprockets" aria-hidden="true" />
    </nav>
  )
}

function Frame({ step: s, onClick }) {
  const state = s.current ? 'NOW' : s.done ? 'DONE' : null
  return (
    <button type="button" onClick={onClick} disabled={!s.unlocked}
      aria-current={s.current ? 'step' : undefined}
      title={s.unlocked ? s.long : `${s.long} — finish the previous step first`}
      className={cx('group flex h-14 w-full flex-col justify-center rounded-md px-2 text-left transition-[background-color,transform] duration-200 sm:h-[4.4rem] sm:rounded-lg sm:px-4',
        s.current ? 'bg-vh-accent text-vh-ink'
          : s.done ? 'bg-vh-cream text-vh-night hover:-translate-y-0.5'
            : s.unlocked ? 'bg-vh-frame text-vh-cream hover:bg-[#3a3a3a]' : 'cursor-not-allowed bg-vh-frame text-vh-cream')}>
      <span className="font-mono text-[10px] font-medium tracking-[0.06em] sm:text-[12px]">
        {s.number}{state && <span className="hidden sm:inline"> · {state}</span>}
        {!s.unlocked && <Lock size={10} className="ml-1 hidden align-[-1px] opacity-60 sm:inline" />}
      </span>
      <span className="display mt-0.5 truncate text-[1.05rem] leading-none sm:text-[1.9rem]">{s.label}</span>
    </button>
  )
}

// ── Account menu ──────────────────────────────────────────────────────────────

function initials(name = '') {
  return name.trim().split(/\s+/).slice(0, 2).map((w) => w[0]?.toUpperCase()).join('') || 'U'
}

function UserMenu({ user, onLogout, navigate }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  useEffect(() => {
    if (!open) return undefined
    const close = (e) => { if (!ref.current?.contains(e.target)) setOpen(false) }
    const esc = (e) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', esc)
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', esc) }
  }, [open])
  if (!user) return null
  const go = (target) => { setOpen(false); navigate(target) }
  return (
    <div className="relative" ref={ref}>
      <button type="button" onClick={() => setOpen((o) => !o)} aria-haspopup="menu" aria-expanded={open} aria-label="Account menu"
        className="flex h-11 w-11 items-center justify-center rounded-full bg-vh-cream text-sm font-bold text-vh-night ring-vh-accent transition hover:ring-4">
        {initials(user.name)}
      </button>
      {open && (
        <div role="menu" className="on-light absolute right-0 top-14 z-50 w-64 rounded-2xl border-2 border-vh-night bg-white p-1.5 shadow-accent animate-fadeIn">
          <div className="px-3 py-2.5">
            <p className="truncate text-sm font-bold">{user.name}</p>
            <p className="truncate font-mono text-xs">{user.email}</p>
          </div>
          <div className="my-1 h-0.5 bg-vh-night/10" />
          <MenuItem icon={FolderOpen} onClick={() => go('library')}>My content</MenuItem>
          <MenuItem icon={CreditCard} onClick={() => go('billing')}>Plan & billing</MenuItem>
          <MenuItem icon={Sparkles} onClick={() => go('pricing')}>Pricing</MenuItem>
          <MenuItem icon={Settings} onClick={() => go('settings')}>Settings</MenuItem>
          <div className="my-1 h-0.5 bg-vh-night/10" />
          <MenuItem icon={LogOut} onClick={onLogout}>Sign out</MenuItem>
        </div>
      )}
    </div>
  )
}

function MenuItem({ icon: Icon, children, onClick, disabled, hint }) {
  return (
    <button type="button" role="menuitem" onClick={onClick} disabled={disabled}
      className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium text-vh-night hover:bg-vh-accent disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent">
      <Icon size={16} strokeWidth={2} />
      <span className="flex-1 text-left">{children}</span>
      {hint && <span className="font-mono text-[11px]">{hint}</span>}
    </button>
  )
}

// ── Navigation drawer (opens from the ☰ button) ───────────────────────────────

function NavDrawer({ onClose, steps, app }) {
  const closeRef = useRef(null)
  useEffect(() => {
    closeRef.current?.focus()
    const esc = (e) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', esc)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.removeEventListener('keydown', esc); document.body.style.overflow = prev }
  }, [onClose])

  const { creatorProfile, screen, navigate, logout, user } = app
  const go = (target) => { navigate(target); onClose() }

  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label="Menu">
      <motion.div className="absolute inset-0 bg-vh-night/60" onClick={onClose}
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.22 }} />
      <motion.aside className="absolute inset-y-0 left-0 flex w-[19rem] max-w-[86vw] flex-col border-r-2 border-vh-night bg-vh-cream"
        initial={{ x: '-100%' }} animate={{ x: 0 }} exit={{ x: '-100%' }} transition={{ duration: 0.32, ease: EASE }}>
        <div className="on-dark flex h-[4.5rem] shrink-0 items-center justify-between bg-vh-night px-4">
          <Logo />
          <IconBtn icon={X} label="Close menu" onClick={onClose} ref={closeRef} className="hover:bg-vh-frame" />
        </div>

        {creatorProfile && (
          <div className="mx-3 mt-4 flex items-center gap-3 rounded-xl border-2 border-vh-night bg-white px-3 py-2.5">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border-2 border-vh-night bg-vh-accent text-sm font-bold">
              {initials(creatorProfile.name || creatorProfile.handle)}
            </span>
            <div className="min-w-0">
              <p className="truncate text-sm font-bold">{creatorProfile.handle}</p>
              <p className="truncate font-mono text-xs">{creatorProfile.niche}</p>
            </div>
          </div>
        )}

        <nav className="flex-1 overflow-y-auto px-3 py-2" aria-label="Main">
          <DrawerItem icon={LayoutDashboard} active={screen === 'dashboard'} disabled={!creatorProfile}
            onClick={() => go('dashboard')}>Studio</DrawerItem>

          <p className="eyebrow mb-1.5 mt-5 px-3">Create</p>
          {steps.map((s) => (
            <DrawerItem key={s.key} number={s.number} active={s.current} done={s.done} disabled={!s.unlocked}
              onClick={() => go(s.target)}>{s.long}</DrawerItem>
          ))}

          <p className="eyebrow mb-1.5 mt-5 px-3">Library</p>
          <DrawerItem icon={FolderOpen} active={screen === 'library'} onClick={() => go('library')}>My content</DrawerItem>
          <DrawerItem icon={CalendarClock} active={screen === 'library-scheduled'} onClick={() => go('library-scheduled')}>Scheduled</DrawerItem>

          <p className="eyebrow mb-1.5 mt-5 px-3">Account</p>
          <DrawerItem icon={CreditCard} active={screen === 'billing'} onClick={() => go('billing')}>Plan & billing</DrawerItem>
          <DrawerItem icon={Settings} active={screen === 'settings'} onClick={() => go('settings')}>Settings</DrawerItem>
        </nav>

        <CreditsMeter billing={app.billing} onUpgrade={() => go('pricing')} />

        <div className="border-t-2 border-vh-night/10 p-3">
          {user && <p className="truncate px-3 pb-2 font-mono text-xs">{user.email}</p>}
          <DrawerItem icon={LogOut} onClick={logout}>Sign out</DrawerItem>
        </div>
      </motion.aside>
    </div>
  )
}

function DrawerItem({ icon: Icon, number, children, active, done, disabled, hint, onClick }) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} aria-current={active ? 'page' : undefined}
      className={cx('mb-1 flex h-10 w-full items-center gap-3 rounded-lg px-3 text-sm font-semibold transition-colors',
        active ? 'bg-vh-accent text-vh-ink'
          : disabled ? 'cursor-not-allowed text-vh-night' : 'text-vh-night hover:bg-white')}>
      {number
        ? <span className="w-5 font-mono text-[11px]">{number}</span>
        : <Icon size={17} strokeWidth={2} />}
      <span className="flex-1 text-left">{children}</span>
      {done && !active && <Check size={15} strokeWidth={3} />}
      {disabled && !hint && number && <Lock size={13} />}
      {hint && <span className="text-[11px]">{hint}</span>}
    </button>
  )
}

// ── Plan pill (header) and credits meter (drawer) ────────────────────────────

function PlanPill({ billing, navigate }) {
  if (!billing) return null
  const free = billing.plan.id === 'free'
  return (
    <button type="button" onClick={() => navigate(free ? 'pricing' : 'billing')}
      className="hidden h-10 items-center rounded-full border-2 border-vh-cream/80 px-4 text-[14px] font-semibold text-vh-cream transition-colors hover:border-vh-accent hover:text-vh-accent sm:flex">
      {billing.plan.name}{free && <span>&nbsp;· Upgrade</span>}
    </button>
  )
}

function CreditsMeter({ billing, onUpgrade }) {
  if (!billing) return null
  const rows = [['script', 'Scripts'], ['render', 'Renders']]
  return (
    <div className="mx-3 mb-3 rounded-xl border-2 border-vh-night bg-white p-3.5">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs font-bold">{billing.plan.name} plan</span>
        {billing.plan.id !== 'pro' && (
          <button type="button" onClick={onUpgrade} className="text-xs font-bold underline underline-offset-2 hover:text-vh-accent2">Upgrade</button>
        )}
      </div>
      {rows.map(([key, label]) => {
        const u = billing.usage[key]
        const pct = u.limit === null ? 6 : u.limit === 0 ? 0 : Math.min(100, Math.round((u.used / u.limit) * 100))
        return (
          <div key={key} className="mb-2.5 last:mb-0">
            <div className="mb-1 flex justify-between font-mono text-[11px]">
              <span>{label}</span>
              <span className="tabular">{u.used} / {u.limit === null ? '∞' : u.limit}</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-vh-night/10">
              <div className={`h-full rounded-full ${pct >= 90 ? 'bg-vh-accent2' : 'bg-vh-accent'}`} style={{ width: `${pct}%` }} />
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ── Soft email verification banner ────────────────────────────────────────────

function VerifyBanner({ email }) {
  const [state, setState] = useState('idle') // idle | sending | sent | error
  const resend = async () => {
    setState('sending')
    try {
      await resendVerification()
      setState('sent')
    } catch {
      setState('error')
    }
  }
  return (
    <div className="border-b-2 border-vh-night bg-vh-accent">
      <div className="mx-auto flex max-w-[90rem] flex-wrap items-center gap-x-3 gap-y-1 px-5 py-2 text-[13px] font-medium text-vh-ink sm:px-8">
        <span className="inline-flex h-5 items-center rounded bg-vh-night px-1.5 font-mono text-[10px] font-bold uppercase tracking-wider text-vh-cream">Verify</span>
        <span>Verify your email to connect Instagram and upgrade later — we sent a link to <span className="font-bold">{email}</span>.</span>
        {state === 'sent'
          ? <span className="font-bold">New link sent.</span>
          : <button type="button" onClick={resend} disabled={state === 'sending'} className="font-bold underline underline-offset-2 disabled:opacity-50">
              {state === 'sending' ? 'Sending…' : state === 'error' ? 'Try again' : 'Resend link'}
            </button>}
      </div>
    </div>
  )
}

export { WORKFLOW }
