import { useState } from 'react'
import { Instagram, ArrowRight, CircleCheck, MailWarning } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { changePassword, logoutEverywhere, resendVerification } from '../../services/api'
import { Alert, Badge, Btn, Card, Input, Page, PageHero, Segmented } from '../../components/ui'

const TABS = [
  { value: 'account', label: 'Account' },
  { value: 'connections', label: 'Connected accounts' },
  { value: 'plan', label: 'Plan' },
]

export default function SettingsScreen() {
  const { user, billing, navigate, logout } = useApp()
  const [tab, setTab] = useState('account')

  return (
    <Page art="settings">
      <PageHero label="Account" title={['Your', 'Settings']} lead={user?.name ? `Signed in as ${user.name}.` : undefined} />
      <div className="mb-8"><Segmented label="Settings section" options={TABS} value={tab} onChange={setTab} /></div>

      {tab === 'account' && <AccountTab user={user} onLoggedOutEverywhere={logout} />}

      {tab === 'connections' && (
        <Card className="flex flex-wrap items-center gap-5 p-6 sm:p-8">
          <span className="flex h-14 w-14 items-center justify-center rounded-xl border-2 border-vh-night bg-vh-accent"><Instagram size={26} /></span>
          <div className="min-w-0 flex-1">
            <p className="display text-[2.2rem]">Instagram</p>
            <p className="text-[15px] leading-relaxed">Import your reels automatically and publish from ViralHook. Needs a Business or Creator account.</p>
          </div>
          <Badge color="muted" size="md">Coming soon</Badge>
        </Card>
      )}

      {tab === 'plan' && billing && (
        <Card tone="dark" className="flex flex-wrap items-center justify-between gap-4 p-6 sm:p-8">
          <div>
            <p className="font-mono text-[13px] font-semibold uppercase tracking-[0.08em] text-vh-accent">Current plan</p>
            <p className="display mt-2 text-[4rem] leading-[0.9] text-vh-accent">{billing.plan.name}</p>
          </div>
          <Btn iconRight={ArrowRight} onClick={() => navigate('billing')}>Plan & usage</Btn>
        </Card>
      )}
    </Page>
  )
}

function AccountTab({ user, onLoggedOutEverywhere }) {
  const [pw, setPw] = useState({ current: '', next: '', repeat: '' })
  const [msg, setMsg] = useState(null)       // { type, text }
  const [busy, setBusy] = useState('')
  const [sent, setSent] = useState(false)
  const set = (k) => (e) => setPw((p) => ({ ...p, [k]: e.target.value }))

  const savePassword = async (e) => {
    e.preventDefault()
    if (pw.next.length < 8) return setMsg({ type: 'error', text: 'New password must be at least 8 characters.' })
    if (pw.next !== pw.repeat) return setMsg({ type: 'error', text: "The two new passwords don't match." })
    setBusy('pw'); setMsg(null)
    try {
      await changePassword(pw.current, pw.next)
      setPw({ current: '', next: '', repeat: '' })
      setMsg({ type: 'success', text: 'Password changed. Other devices were signed out.' })
    } catch (err) {
      setMsg({ type: 'error', text: err.message })
    } finally { setBusy('') }
  }

  return (
    <div className="grid items-start gap-8 lg:grid-cols-2">
      <Card className="p-6 sm:p-8">
        <h2 className="display mb-5 text-[2.4rem]">Profile</h2>
        <dl className="space-y-3 text-[15px]">
          <div className="flex justify-between gap-4 rounded-lg bg-vh-cream px-4 py-3"><dt className="font-mono text-[13px]">Name</dt><dd className="font-bold">{user?.name}</dd></div>
          <div className="flex justify-between gap-4 rounded-lg bg-vh-cream px-4 py-3"><dt className="font-mono text-[13px]">Email</dt><dd className="truncate font-bold">{user?.email}</dd></div>
          <div className="flex items-center justify-between gap-4 rounded-lg bg-vh-cream px-4 py-3">
            <dt className="font-mono text-[13px]">Email status</dt>
            <dd>{user?.emailVerified
              ? <Badge color="ok"><CircleCheck size={12} /> Verified</Badge>
              : <Badge color="warn"><MailWarning size={12} /> Not verified</Badge>}</dd>
          </div>
        </dl>
        {!user?.emailVerified && (
          <Btn className="mt-5" variant="secondary" size="sm" disabled={sent}
            onClick={async () => { await resendVerification().catch(() => {}); setSent(true) }}>
            {sent ? 'Link sent' : 'Resend verification link'}
          </Btn>
        )}
        <div className="mt-6 border-t-2 border-vh-night/10 pt-5">
          <p className="text-[15px] font-semibold">Signed in on a shared computer?</p>
          <Btn className="mt-3" variant="danger" size="sm" loading={busy === 'all'}
            onClick={async () => { setBusy('all'); await logoutEverywhere().catch(() => {}); onLoggedOutEverywhere() }}>
            Sign out everywhere
          </Btn>
        </div>
      </Card>

      <Card className="p-6 sm:p-8">
        <h2 className="display mb-5 text-[2.4rem]">Change password</h2>
        <form onSubmit={savePassword} className="space-y-4">
          <Input label="Current password" type="password" autoComplete="current-password" value={pw.current} onChange={set('current')} required />
          <Input label="New password" type="password" autoComplete="new-password" value={pw.next} onChange={set('next')} hint="At least 8 characters" required />
          <Input label="Repeat new password" type="password" autoComplete="new-password" value={pw.repeat} onChange={set('repeat')} required />
          {msg && <Alert type={msg.type}>{msg.text}</Alert>}
          <Btn type="submit" loading={busy === 'pw'}>Save password</Btn>
        </form>
      </Card>
    </div>
  )
}
