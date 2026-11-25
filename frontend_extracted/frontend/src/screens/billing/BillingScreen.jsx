import { useEffect, useState } from 'react'
import { FileText, Clapperboard, Radar, ArrowRight, CalendarClock, Receipt, FlaskConical } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { cancelSubscription, getUsageHistory, resumeSubscription } from '../../services/api'
import { Alert, Badge, Btn, Card, EmptyState, Modal, Page, PageHero, SectionTitle } from '../../components/ui'
import { Stagger, StaggerItem, CountUp } from '../../components/motion'
import { money } from './PricingScreen'

const METERS = [
  ['script', 'Script generations', FileText],
  ['render', 'Video renders', Clapperboard],
  ['research', 'Research runs', Radar],
]
const date = (iso) => (iso ? new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '—')
const when = (iso) => new Date(iso).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })

export default function BillingScreen() {
  const { billing, refreshBilling, navigate } = useApp()
  const [events, setEvents] = useState([])
  const [confirmCancel, setConfirmCancel] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    refreshBilling()
    getUsageHistory().then((r) => setEvents(r.events)).catch(() => setEvents([]))
  }, [refreshBilling])

  if (!billing) return null
  const { plan, usage, period, subscription, demoPayments } = billing
  const price = plan.prices.PKR[subscription?.interval || 'month']

  const run = async (fn) => {
    setBusy(true); setError('')
    try { await fn(); await refreshBilling() } catch (e) { setError(e.message) } finally { setBusy(false); setConfirmCancel(false) }
  }

  return (
    <Page art="billing">
      <PageHero label="Account" title={['Plan &', 'Usage']}
        lead={`Usage resets on ${date(period.end)}. Failed jobs never use a credit.`} />

      {error && <Alert type="error" className="mb-6 max-w-3xl">{error}</Alert>}
      {demoPayments && (
        <Alert type="info" chip="Demo" className="mb-8">
          <span className="inline-flex items-center gap-1.5"><FlaskConical size={15} /> Payments run in demo mode — no real money moves until a payment provider is connected.</span>
        </Alert>
      )}

      <div className="grid items-stretch gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        {/* current plan */}
        <Card tone="dark" className="flex flex-col p-6 sm:p-8">
          <div className="flex items-center justify-between gap-2">
            <span className="font-mono text-[13px] font-semibold uppercase tracking-[0.08em] text-vh-accent">Current plan</span>
            {subscription?.cancelAtPeriodEnd ? <Badge color="warn">Ends {date(subscription.currentPeriodEnd)}</Badge>
              : subscription ? <Badge color="ok">Active</Badge> : <Badge color="muted">Free</Badge>}
          </div>
          <p className="display mt-4 text-[clamp(4rem,8vw,5.6rem)] leading-[0.85] text-vh-accent">{plan.name}</p>
          <p className="mt-3 text-[16px]">
            {subscription ? <>{money(price, 'PKR')} / {subscription.interval} · {subscription.cancelAtPeriodEnd ? 'ends' : 'renews'} {date(subscription.currentPeriodEnd)}</>
              : 'No payment needed. Upgrade any time for more credits.'}
          </p>
          <div className="flex-1" />
          <div className="mt-7 flex flex-wrap gap-3">
            <Btn iconRight={ArrowRight} onClick={() => navigate('pricing')}>{subscription ? 'Change plan' : 'Upgrade'}</Btn>
            {subscription && !subscription.cancelAtPeriodEnd && (
              <Btn variant="secondary" onClick={() => setConfirmCancel(true)}>Cancel plan</Btn>
            )}
            {subscription?.cancelAtPeriodEnd && (
              <Btn variant="secondary" loading={busy} onClick={() => run(resumeSubscription)}>Keep my plan</Btn>
            )}
          </div>
        </Card>

        {/* usage meters */}
        <Card className="p-6 sm:p-8">
          <div className="mb-6 flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="display text-[2.4rem]">This period</h2>
            <span className="flex items-center gap-1.5 font-mono text-[13px]"><CalendarClock size={14} /> {date(period.start)} – {date(period.end)}</span>
          </div>
          <Stagger className="space-y-6">
            {METERS.map(([key, label, Icon]) => {
              const u = usage[key]
              const unlimited = u.limit === null
              const pct = unlimited ? 8 : u.limit === 0 ? 0 : Math.min(100, Math.round((u.used / u.limit) * 100))
              const tone = !unlimited && u.limit > 0 && pct >= 90 ? 'bg-vh-accent2' : 'bg-vh-accent'
              return (
                <StaggerItem key={key}>
                  <div className="mb-2 flex items-baseline justify-between gap-3">
                    <span className="flex items-center gap-2 text-[16px] font-semibold"><Icon size={17} />{label}</span>
                    <span className="font-mono text-[14px] tabular">
                      <span className="display text-[1.8rem]"><CountUp value={u.used} /></span>
                      {' / '}{unlimited ? '∞' : u.limit === 0 ? 'not included' : u.limit}
                    </span>
                  </div>
                  <div className="h-4 overflow-hidden rounded-full border-2 border-vh-night bg-vh-cream">
                    <div className={`h-full transition-[width] duration-700 ${tone} ${unlimited ? 'opacity-50' : ''}`} style={{ width: `${pct}%` }} />
                  </div>
                </StaggerItem>
              )
            })}
          </Stagger>
        </Card>
      </div>

      <div className="mt-12 grid items-start gap-8 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <section>
          <SectionTitle>Recent usage</SectionTitle>
          {events.length === 0 ? (
            <Card shadow={false}><EmptyState title="Nothing used yet">Scripts, renders and research runs will show up here.</EmptyState></Card>
          ) : (
            <ul className="space-y-3">
              {events.map((e, i) => {
                const [, label, Icon] = METERS.find(([k]) => k === e.meter) || ['', e.meter, FileText]
                return (
                  <li key={i} className="flex items-center gap-4 rounded-xl border-2 border-vh-night bg-white px-4 py-3">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-vh-night text-vh-accent"><Icon size={17} /></span>
                    <div className="min-w-0 flex-1">
                      <p className="text-[15px] font-bold">{label}</p>
                      {e.note && <p className="truncate text-[13px]">{e.note}</p>}
                    </div>
                    <span className="shrink-0 font-mono text-[12px]">{when(e.at)}</span>
                  </li>
                )
              })}
            </ul>
          )}
        </section>
        <section>
          <SectionTitle>Receipts</SectionTitle>
          <Card shadow={false}><EmptyState icon={Receipt} title="No receipts yet">They appear here once a real payment provider is connected.</EmptyState></Card>
        </section>
      </div>

      <Modal open={confirmCancel} onClose={() => setConfirmCancel(false)} title={`Cancel ${plan.name}?`}>
        <p className="text-[15px] leading-relaxed">
          You keep {plan.name} until <span className="font-bold">{date(subscription?.currentPeriodEnd)}</span>, then move to Free.
          You can change your mind any time before then.
        </p>
        <div className="mt-6 flex justify-end gap-2">
          <Btn variant="ghost" onClick={() => setConfirmCancel(false)}>Keep plan</Btn>
          <Btn variant="danger" loading={busy} onClick={() => run(cancelSubscription)}>Cancel at period end</Btn>
        </div>
      </Modal>
    </Page>
  )
}
