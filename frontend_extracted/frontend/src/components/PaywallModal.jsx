// Shown anywhere in the app when the backend answers 402 (a plan limit is used
// up): what ran out, when it resets, and what the next plan includes.
import { useEffect, useState } from 'react'
import { Gauge, ArrowRight } from 'lucide-react'
import { useApp } from '../context/AppContext'
import { getPlans } from '../services/api'
import { Btn, Modal } from './ui'

const WHAT = { script: 'script generations', render: 'video renders', research: 'research runs' }

export default function PaywallModal() {
  const { navigate, refreshBilling } = useApp()
  const [info, setInfo] = useState(null)
  const [plans, setPlans] = useState([])

  useEffect(() => {
    const onLimit = (e) => {
      setInfo(e.detail)
      refreshBilling()
      if (!plans.length) getPlans().then((r) => setPlans(r.plans)).catch(() => {})
    }
    window.addEventListener('vh:out-of-credits', onLimit)
    return () => window.removeEventListener('vh:out-of-credits', onLimit)
  }, [plans.length, refreshBilling])

  const next = info ? plans[plans.findIndex((p) => p.id === info.plan) + 1] : null
  const nextLimit = next?.limits?.[info?.meter]
  const resets = info?.resetsAt ? new Date(info.resetsAt).toLocaleDateString('en-GB', { day: 'numeric', month: 'long' }) : null

  return (
    <Modal open={!!info} onClose={() => setInfo(null)} title="You've reached your plan limit">
      {info && (
        <>
          <div className="flex items-start gap-4">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-vh-accent2/12 text-vh-accent2"><Gauge size={22} /></span>
            <div>
              <p className="text-sm leading-relaxed text-vh-text">{info.message}</p>
              {info.limit > 0 && resets && <p className="mt-1 text-xs text-vh-muted">Your {WHAT[info.meter]} reset on {resets}.</p>}
            </div>
          </div>
          {next && (
            <div className="mt-5 flex items-center justify-between gap-4 rounded-xl border border-vh-accent/30 bg-vh-accent/[0.06] px-4 py-3">
              <div>
                <p className="text-sm font-semibold text-vh-head">{next.name}</p>
                <p className="text-xs text-vh-muted">{nextLimit === null ? 'Unlimited' : nextLimit} {WHAT[info.meter]} / month</p>
              </div>
              <span className="text-right text-xs text-vh-muted">{next.tagline}</span>
            </div>
          )}
          <div className="mt-6 flex justify-end gap-2">
            <Btn variant="ghost" onClick={() => setInfo(null)}>Not now</Btn>
            <Btn iconRight={ArrowRight} onClick={() => { setInfo(null); navigate('pricing') }}>See plans</Btn>
          </div>
        </>
      )}
    </Modal>
  )
}
