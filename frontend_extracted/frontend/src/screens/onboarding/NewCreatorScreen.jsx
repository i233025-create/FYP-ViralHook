import { useState } from 'react'
import { ArrowLeft, ArrowRight } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { createNewCreatorProfile } from '../../services/api'
import { Btn, Card, Input, Select, Textarea, Alert, Page, PageHero } from '../../components/ui'
import { NICHES } from '../../data/mockData'

const NEXT = [
  ['Trend research', 'What works in your niche right now, measured on real videos.'],
  ['Scored scripts', 'Three scripts per idea, scored for hook, structure and timing.'],
  ['Your style, later', 'Upload a few videos any time and scripts start sounding like you.'],
]

export default function NewCreatorScreen() {
  const { setCreatorProfile, navigate, user } = useApp()
  const [form, setForm] = useState({
    name: user?.name || '',
    handle: user?.handle || '',
    niche: NICHES[0],
    contentPreferences: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    if (!form.name.trim() || !form.handle.trim()) { setError('Name and handle are required.'); return }
    setLoading(true)
    try {
      const { profile } = await createNewCreatorProfile(form)
      setCreatorProfile(profile)
      navigate('dashboard')
    } catch {
      setError('Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Page art="onboarding">
      <button type="button" onClick={() => navigate('creator-type')}
        className="mb-6 inline-flex items-center gap-1.5 text-[15px] font-semibold underline-offset-4 hover:underline">
        <ArrowLeft size={16} /> All options
      </button>
      <PageHero
        step="03"
        label="Set up"
        title={['New', 'Creator']}
        lead="Tell us what you want to make. Once you have a few videos, upload them and your scripts will start matching your real style."
      />

      <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <Card className="p-6 sm:p-8">
          <h2 className="display text-[2.4rem]">Your profile</h2>
          <form onSubmit={submit} className="mt-5 space-y-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <Input label="Your name" value={form.name} onChange={set('name')} placeholder="Hamza Bhatti" required />
              <Input label="Handle" value={form.handle} onChange={set('handle')} placeholder="@hamzaeats" required />
            </div>
            <Select label="Content niche" value={form.niche} onChange={set('niche')} options={NICHES} />
            <Textarea
              label="What do you want to make? (optional)"
              value={form.contentPreferences}
              onChange={set('contentPreferences')}
              placeholder="e.g. Short food reviews of street stalls in Lahore, honest and funny, in Urdu–English."
              rows={4}
            />
            {error && <Alert type="error">{error}</Alert>}
            <div className="flex justify-end">
              <Btn type="submit" size="lg" loading={loading} iconRight={ArrowRight}>Create profile</Btn>
            </div>
          </form>
        </Card>

        <Card tone="dark" className="p-6 sm:p-8">
          <p className="font-mono text-[13px] font-semibold uppercase tracking-[0.08em] text-vh-accent">What you get</p>
          <h2 className="display mt-3 text-[2.6rem]">Ready in 30 seconds</h2>
          <ol className="mt-5 space-y-4">
            {NEXT.map(([title, text], i) => (
              <li key={title} className="flex gap-4">
                <span className="display w-9 shrink-0 text-[2.2rem] leading-none text-vh-accent">{String(i + 1).padStart(2, '0')}</span>
                <div>
                  <p className="text-[17px] font-bold">{title}</p>
                  <p className="mt-0.5 text-[15px] leading-relaxed">{text}</p>
                </div>
              </li>
            ))}
          </ol>
        </Card>
      </div>
    </Page>
  )
}
