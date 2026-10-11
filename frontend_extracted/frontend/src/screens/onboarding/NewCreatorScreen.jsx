import { useState } from 'react'
import { Sparkles, ArrowLeft } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { createNewCreatorProfile } from '../../services/api'
import { Btn, Input, Select, Textarea, Alert, SectionHeader } from '../../components/ui'
import { NICHES } from '../../data/mockData'

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
    <div className="flex h-screen w-screen bg-discord-dark items-center justify-center p-6 overflow-y-auto">
      <div className="w-full max-w-lg">
        <button onClick={() => navigate('creator-type')} className="flex items-center gap-1.5 text-discord-muted hover:text-discord-white text-sm mb-6 transition-colors">
          <ArrowLeft size={16} /> Back
        </button>

        <SectionHeader
          icon={Sparkles}
          title="Set up your creator profile"
          subtitle="Tell us about yourself so ViralHook can personalise your content experience."
        />

        <form onSubmit={submit} className="space-y-4 bg-discord-sidebar border border-discord-faint/25 rounded-2xl p-6">
          <div className="grid grid-cols-2 gap-4">
            <Input label="Your name" value={form.name} onChange={set('name')} placeholder="Alex Rivera" required />
            <Input label="Handle / username" value={form.handle} onChange={set('handle')} placeholder="@alexcreates" required />
          </div>
          <Select
            label="Content niche"
            value={form.niche}
            onChange={set('niche')}
            options={NICHES}
          />
          <Textarea
            label="Content preferences & ideas (optional)"
            value={form.contentPreferences}
            onChange={set('contentPreferences')}
            placeholder="e.g. I want to make educational tech shorts, focus on beginner-friendly AI tutorials..."
            rows={4}
          />

          {error && <Alert type="error">{error}</Alert>}

          <Btn type="submit" size="lg" loading={loading} className="w-full">
            Create My Profile
          </Btn>
        </form>
      </div>
    </div>
  )
}
