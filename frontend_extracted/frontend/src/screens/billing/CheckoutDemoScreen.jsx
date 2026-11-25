import { useEffect, useState } from 'react'
import { CreditCard, ShieldCheck, CircleCheck, CircleX, ArrowRight, FlaskConical } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { completeDemoCheckout, getCheckout } from '../../services/api'
import { Alert, Btn, Spinner, StepChip } from '../../components/ui'
import { PageDecor } from '../../components/art'
import Logo from '../../components/brand/Logo'
import { money } from './PricingScreen'

/**
 * Stand-in for a payment provider's hosted checkout (PAYMENT_PROVIDER=demo):
 * no card is charged. "Pay" / "Simulate a failure" do what the provider's
 * webhook would. With a real provider, the browser goes to their page instead.
 */
export default function CheckoutDemoScreen() {
  const { checkoutSession, linkToken, navigate, refreshBilling } = useApp()
  const sessionId = checkoutSession || linkToken
  const [session, setSession] = useState(null)
  const [state, setState] = useState('loading') // loading | open | paying | paid | failed | error
  const [error, setError] = useState('')

  useEffect(() => {
    if (window.location.pathname.startsWith('/checkout')) window.history.replaceState(null, '', '/')
    if (!sessionId) { setState('error'); setError('This checkout link is incomplete.'); return }
    getCheckout(sessionId)
      .then((s) => { setSession(s); setState(s.status === 'open' ? 'open' : s.status) })
      .catch((e) => { setError(e.message); setState('error') })
  }, [sessionId])

  const finish = async (outcome) => {
    setState('paying')
    try {
      const { status } = await completeDemoCheckout(sessionId, outcome)
      await refreshBilling()
      setState(status)
    } catch (e) {
      setError(e.message)
      setState('error')
    }
  }

  const planName = session ? session.plan[0].toUpperCase() + session.plan.slice(1) : ''

  return (
    <div className="flex min-h-[100dvh] flex-col">
      <header className="on-dark shrink-0 bg-vh-night">
        <div className="mx-auto flex h-[4.5rem] max-w-[90rem] items-center justify-between px-4 sm:px-8">
          <Logo />
          <span className="flex items-center gap-1.5 font-mono text-[13px] text-vh-cream"><ShieldCheck size={16} className="text-vh-accent" /> Secure checkout</span>
        </div>
        <div className="mx-auto max-w-[90rem] px-4 pb-3 sm:px-8"><div className="sprockets" aria-hidden="true" /></div>
      </header>

      <main className="relative isolate flex flex-1 items-start justify-center overflow-hidden px-4 pb-48 pt-10 sm:px-8 lg:items-center">
        <PageDecor kind="billing" />
        <div className="w-full max-w-4xl animate-rise">
          {state === 'loading' && <div className="flex justify-center py-20"><Spinner size={30} /></div>}

          {state === 'error' && (
            <div className="mx-auto max-w-md space-y-4">
              <Alert type="error">{error}</Alert>
              <Btn variant="secondary" onClick={() => navigate('pricing')}>Back to plans</Btn>
            </div>
          )}

          {(state === 'open' || state === 'paying') && session && (
            <>
              <Alert type="warning" chip="Demo" className="mb-7">
                <span className="inline-flex items-center gap-1.5"><FlaskConical size={15} /> Demo payment — no real card is charged. A real provider plugs in later.</span>
              </Alert>
              <div className="grid items-stretch gap-8 md:grid-cols-2">
                <section className="on-dark overflow-hidden rounded-2xl bg-vh-night shadow-accent">
                  <div className="clapper h-9" aria-hidden="true" />
                  <div className="p-7">
                    <StepChip label="Order summary" />
                    <p className="display mt-5 text-[3rem] leading-[0.95]">ViralHook <span className="text-vh-accent">{planName}</span></p>
                    <p className="display mt-4 text-[4.4rem] leading-[0.85] text-vh-accent">{money(session.amount, session.currency)}</p>
                    <p className="mt-3 font-mono text-[14px]">Billed every {session.interval} · cancel anytime</p>
                  </div>
                </section>

                <div className="flex flex-col rounded-2xl border-2 border-vh-night bg-white p-7 shadow-hard">
                  <h2 className="display text-[2.6rem]">Payment</h2>
                  <div className="mt-4 rounded-xl border-2 border-vh-night bg-vh-cream p-5">
                    <p className="flex items-center gap-2 text-[15px] font-bold"><CreditCard size={18} /> Test card</p>
                    <p className="mt-3 font-mono text-[17px] tracking-[0.18em]">4242 4242 4242 4242</p>
                    <div className="mt-3 h-3 w-24 rounded bg-vh-accent" aria-hidden="true" />
                  </div>
                  <div className="flex-1" />
                  <Btn size="lg" className="mt-7 w-full" loading={state === 'paying'} onClick={() => finish('paid')}>
                    Pay {money(session.amount, session.currency)}
                  </Btn>
                  <button type="button" disabled={state === 'paying'} onClick={() => finish('failed')}
                    className="mt-4 w-full text-center text-[14px] font-semibold underline underline-offset-4 hover:text-vh-accent2 disabled:opacity-50">
                    Simulate a failed payment
                  </button>
                </div>
              </div>
            </>
          )}

          {state === 'paid' && (
            <Result icon={CircleCheck} tone="ok" title={`You're on ${planName}`}
              text="Your new limits are active right away. A receipt will be emailed once a real payment provider is connected.">
              <Btn size="lg" iconRight={ArrowRight} onClick={() => navigate('dashboard')}>Go to studio</Btn>
              <Btn variant="secondary" onClick={() => navigate('billing')}>View plan & usage</Btn>
            </Result>
          )}

          {state === 'failed' && (
            <Result icon={CircleX} tone="bad" title="Payment didn't go through"
              text="Nothing was charged and your plan hasn't changed. You can try again or choose another plan.">
              <Btn size="lg" onClick={() => navigate('pricing')}>Back to plans</Btn>
            </Result>
          )}
        </div>
      </main>
    </div>
  )
}

function Result({ icon: Icon, tone, title, text, children }) {
  return (
    <div className="mx-auto max-w-lg rounded-2xl border-2 border-vh-night bg-white p-8 text-center shadow-hard">
      <span className={`mx-auto flex h-16 w-16 items-center justify-center rounded-full border-2 border-vh-night ${tone === 'ok' ? 'bg-vh-accent' : 'bg-vh-accent2 text-white'}`}>
        <Icon size={30} strokeWidth={2} />
      </span>
      <h1 className="display mt-5 text-[2.8rem]">{title}</h1>
      <p className="mt-2 text-[15px] leading-relaxed">{text}</p>
      <div className="mt-7 flex flex-col gap-3 sm:flex-row sm:justify-center">{children}</div>
    </div>
  )
}
