import { useState } from 'react'
import { Zap, Mail, Lock, User } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { loginUser, signupUser } from '../../services/api'
import { Btn, Input, Divider, Alert } from '../../components/ui'

export default function AuthScreen() {
  const { setUser, navigate } = useApp()
  const [mode, setMode] = useState('login') // 'login' | 'signup'
  const [form, setForm] = useState({ name: '', email: 'demo@viralhook.ai', password: 'demo1234' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = mode === 'login'
        ? await loginUser({ email: form.email, password: form.password })
        : await signupUser({ name: form.name, email: form.email, password: form.password })
      setUser(res.user)
      navigate('creator-type')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-screen w-screen bg-discord-dark overflow-hidden">
      {/* Left panel — branding */}
      <div className="hidden lg:flex flex-col justify-between w-[480px] min-w-[480px] bg-discord-sidebar border-r border-discord-faint/20 p-12">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-discord-blurple">
            <Zap size={20} className="text-white" />
          </div>
          <span className="text-discord-white font-bold text-xl">ViralHook</span>
        </div>

        <div>
          <h1 className="text-discord-white font-bold text-4xl leading-tight mb-4">
            AI-Driven Content<br />Production Studio
          </h1>
          <p className="text-discord-muted text-base leading-relaxed mb-8">
            From creator style analysis to trending research, personalised scripts, and export-ready timelines — all in one workflow.
          </p>
          <div className="space-y-3">
            {[
              'Creator style extraction from your existing videos',
              'Real-time trend research matched to your niche',
              'Multi-variant script generation with evaluation',
              'Production timeline & Adobe Premiere XML export',
            ].map((f) => (
              <div key={f} className="flex items-start gap-2.5">
                <div className="w-1.5 h-1.5 rounded-full bg-discord-blurple mt-1.5 flex-shrink-0" />
                <p className="text-discord-muted text-sm">{f}</p>
              </div>
            ))}
          </div>
        </div>

        <p className="text-discord-faint text-xs">Final Year Project — ViralHook v1.0 Frontend Prototype</p>
      </div>

      {/* Right panel — form */}
      <div className="flex flex-1 items-center justify-center p-6">
        <div className="w-full max-w-sm">
          {/* Mobile logo */}
          <div className="flex items-center gap-2 mb-8 lg:hidden">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-discord-blurple">
              <Zap size={16} className="text-white" />
            </div>
            <span className="text-discord-white font-bold">ViralHook</span>
          </div>

          <h2 className="text-discord-white font-bold text-2xl mb-1">
            {mode === 'login' ? 'Welcome back' : 'Create account'}
          </h2>
          <p className="text-discord-muted text-sm mb-6">
            {mode === 'login' ? "Sign in to continue to your workspace." : 'Get started with ViralHook.'}
          </p>

          {/* Demo hint */}
          {mode === 'login' && (
            <Alert type="info">
              <span className="font-semibold">Demo credentials:</span>{' '}
              demo@viralhook.ai / demo1234
            </Alert>
          )}

          <form onSubmit={submit} className="space-y-4 mt-5">
            {mode === 'signup' && (
              <Input label="Full name" value={form.name} onChange={set('name')} placeholder="Alex Rivera" required />
            )}
            <Input label="Email" type="email" value={form.email} onChange={set('email')} placeholder="you@example.com" required />
            <Input label="Password" type="password" value={form.password} onChange={set('password')} placeholder="••••••••" required />

            {error && <Alert type="error">{error}</Alert>}

            <Btn type="submit" size="lg" loading={loading} className="w-full mt-2">
              {mode === 'login' ? 'Sign In' : 'Create Account'}
            </Btn>
          </form>

          <Divider label="or" />

          <button
            onClick={() => { setMode(mode === 'login' ? 'signup' : 'login'); setError('') }}
            className="w-full text-center text-discord-muted text-sm hover:text-discord-white transition-colors"
          >
            {mode === 'login' ? "Don't have an account? Sign up" : 'Already have an account? Sign in'}
          </button>
        </div>
      </div>
    </div>
  )
}
