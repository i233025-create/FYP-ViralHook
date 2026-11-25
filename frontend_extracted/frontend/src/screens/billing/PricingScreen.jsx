import { useEffect, useState } from 'react'
import { Check, Minus, ArrowRight, FileText, Clapperboard, Radar } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { getPlans, startCheckout } from '../../services/api'
import { Alert, Badge, Btn, Page, PageHero, Segmented, SectionTitle } from '../../components/ui'
import { Stagger, StaggerItem } from '../../components/motion'
import { PublicHeader } from '../landing/LandingScreen'

export const money = (amount, currency) => (amount === 0 ? 'Free'
  : currency === 'PKR' ? `Rs ${amount.toLocaleString('en-PK')}` : `$${amount}`)
const limitText = (v) => (v === null ? 'Unlimited' : v === 0 ? 'Not included' : `${v} / month`)

const FEATURE_ROWS = [
  ['Script generations', (p) => limitText(p.limits.script)],
  ['AI video renders', (p) => limitText(p.limits.render)],
  ['Research runs', (p) => limitText(p.limits.research)],
  ['Premiere XML export', (p) => p.features.xml_export],
  ['Your photos in videos', (p) => p.features.creator_photos],
  ['Instagram publishing', (p) => p.features.publish],
  ['Scheduled posts', (p) => p.features.schedule],
  ['Creator profiles', (p) => String(p.features.profiles)],
]

const FAQ = [
  ['What counts as a credit?', 'Each successful script generation, video render or research run uses one. If a job fails, the credit is given back.'],
  ['Do unused credits roll over?', 'No — limits reset at the start of each billing period.'],
  ['Can I cancel anytime?', 'Yes. Your plan stays active until the end of the period you paid for, then you move to Free.'],
  ['Why do I need to verify my email to pay?', 'So receipts and account notices reach you, and so nobody can buy a plan on an account they do not own.'],
]

export default function PricingScreen() {
  const { user, billing, navigate, setCheckoutSession } = useApp()
  const [plans, setPlans] = useState([])
  const [interval, setInterval] = useState('month')
  const [currency, setCurrency] = useState('PKR')
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const current = billing?.plan?.id

  useEffect(() => { getPlans().then((r) => setPlans(r.plans)).catch((e) => setError(e.message)) }, [])

  const choose = async (plan) => {
    setError('')
    if (!user) { navigate('auth-signup'); return }
    if (plan.id === 'free') { navigate('dashboard'); return }
    setBusy(plan.id)
    try {
      const res = await startCheckout({ plan: plan.id, interval, currency })
      if (res.demo) {               // our own demo checkout page, opened in the app
        setCheckoutSession(res.sessionId)
        navigate('checkout-demo')
      } else {
        window.location.assign(res.url)   // a real provider's hosted checkout
      }
    } catch (e) {
      setError(e.status === 403 ? 'Please verify your email first — use "Resend link" in the banner at the top.' : e.message)
    } finally {
      setBusy('')
    }
  }

  const content = (
    <Page art="billing">
      <PageHero
        label="Pricing"
        title={['Pick your', 'Pace']}
        lead="Start free with your own style. Upgrade when you post more — every plan uses the same models and the same honest scores."
        aside={
          <div className="flex flex-wrap gap-2">
            <Segmented label="Billing interval" value={interval} onChange={setInterval} size="sm"
              options={[{ value: 'month', label: 'Monthly' }, { value: 'year', label: 'Yearly · 2 months free' }]} />
            <Segmented label="Currency" value={currency} onChange={setCurrency} size="sm"
              options={[{ value: 'PKR', label: 'PKR' }, { value: 'USD', label: 'USD' }]} />
          </div>
        }
      />

      {error && <Alert type="error" className="mb-6 max-w-3xl">{error}</Alert>}

      <Stagger className="grid gap-7 lg:grid-cols-3">
        {plans.map((plan) => {
          const price = plan.prices[currency][interval]
          const isCurrent = current === plan.id
          const dark = plan.highlight
          return (
            <StaggerItem key={plan.id} className="grid">
              <div className={`relative flex flex-col rounded-2xl border-2 border-vh-night p-7 sm:p-8
                ${dark ? 'on-dark bg-vh-night shadow-accent' : 'bg-white shadow-hard'}`}>
                <div className="flex min-h-[1.75rem] items-center justify-between gap-2">
                  <span className={`font-mono text-[13px] font-bold uppercase tracking-[0.1em] ${dark ? 'text-vh-accent' : 'text-vh-accent2'}`}>{plan.name}</span>
                  <span className="flex gap-1.5">
                    {plan.highlight && <Badge color="pop">Most popular</Badge>}
                    {isCurrent && <Badge color="accent">Current plan</Badge>}
                  </span>
                </div>
                <p className="mt-4 flex items-baseline gap-2">
                  <span className={`display text-[4.4rem] leading-[0.85] ${dark ? 'text-vh-accent' : ''}`}>{money(price, currency)}</span>
                  {price > 0 && <span className="font-mono text-[14px]">/ {interval}</span>}
                </p>
                <p className="mt-3 min-h-[3rem] text-[15px] leading-relaxed">{plan.tagline}</p>

                <dl className="mt-5 grid grid-cols-3 gap-2.5">
                  {[[FileText, 'Scripts', plan.limits.script], [Clapperboard, 'Renders', plan.limits.render], [Radar, 'Research', plan.limits.research]]
                    .map(([Icon, label, v]) => (
                      <div key={label} className={`flex flex-col-reverse rounded-xl bg-vh-raised px-2 py-3 text-center ${v === 0 ? 'border-2 border-dashed border-vh-edge bg-transparent' : ''}`}>
                        <dt className="mt-1 flex items-center justify-center gap-1 font-mono text-[11px]"><Icon size={11} />{label}</dt>
                        <dd className="display text-[2.2rem] leading-none tabular">{v === null ? '∞' : v}</dd>
                      </div>
                    ))}
                </dl>

                <ul className="mt-6 flex-1 space-y-2.5 text-[15px]">
                  {[['Premiere XML export', plan.features.xml_export], ['Your photos in videos', plan.features.creator_photos],
                    ['Instagram publishing', plan.features.publish], ['Scheduled posts', plan.features.schedule]].map(([t, on]) => (
                    <li key={t} className={`flex items-center gap-2.5 font-medium ${on ? '' : 'line-through decoration-2'}`}>
                      {on ? <Check size={17} strokeWidth={3} className={dark ? 'text-vh-accent' : ''} /> : <Minus size={17} />}{t}
                    </li>
                  ))}
                </ul>

                <Btn className="mt-8 w-full" size="lg" variant={dark ? 'primary' : 'secondary'}
                  disabled={isCurrent} loading={busy === plan.id} onClick={() => choose(plan)} iconRight={isCurrent ? null : ArrowRight}>
                  {isCurrent ? 'Your plan' : plan.id === 'free' ? (user ? 'Stay on Free' : 'Start free') : `Get ${plan.name}`}
                </Btn>
              </div>
            </StaggerItem>
          )
        })}
      </Stagger>

      {plans.length > 0 && (
        <section className="mt-16">
          <SectionTitle>Compare plans</SectionTitle>
          <div className="overflow-x-auto rounded-2xl border-2 border-vh-night bg-white">
            <table className="w-full min-w-[34rem] text-[15px]">
              <thead>
                <tr className="bg-vh-night text-left text-vh-cream">
                  <th className="px-5 py-3.5 font-mono text-[13px] font-semibold uppercase tracking-[0.06em]">Feature</th>
                  {plans.map((p) => <th key={p.id} className="display px-5 py-3 text-[1.7rem] font-normal">{p.name}</th>)}
                </tr>
              </thead>
              <tbody className="divide-y divide-vh-night/15">
                {FEATURE_ROWS.map(([label, get]) => (
                  <tr key={label}>
                    <td className="px-5 py-3.5 font-semibold">{label}</td>
                    {plans.map((p) => {
                      const v = get(p)
                      return (
                        <td key={p.id} className="px-5 py-3.5">
                          {v === true ? <Check size={17} strokeWidth={3} />
                            : v === false ? <Minus size={17} />
                              : <span className={v === 'Not included' ? 'line-through decoration-2' : 'font-medium'}>{v}</span>}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="mt-16">
        <SectionTitle>Questions</SectionTitle>
        <div className="space-y-3">
          {FAQ.map(([q, a]) => (
            <details key={q} className="group rounded-xl border-2 border-vh-night bg-white px-5 py-4 open:shadow-hard-sm">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-[16px] font-bold">
                {q}<span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-vh-accent text-lg leading-none transition-transform group-open:rotate-45">+</span>
              </summary>
              <p className="mt-2 text-[15px] leading-relaxed">{a}</p>
            </details>
          ))}
        </div>
        <p className="mt-6 font-mono text-[13px]">Prices are placeholders while the team finalises them.</p>
      </section>
    </Page>
  )

  // Signed-out visitors (from the landing page) get the public header instead of the app shell
  return user ? content : <><PublicHeader />{content}</>
}
