import { useState } from 'react'
import { Zap } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { USE_REAL_BACKEND, loginUser, signupUser, requestPasswordReset } from '../../services/api'
import { Btn, Input, Divider, Alert } from '../../components/ui'

const MIN_PASSWORD = 8

const COPY = {
  login:  { title: 'Welcome back',    subtitle: 'Sign in to continue to your workspace.', button: 'Sign In' },
  signup: { title: 'Create account',  subtitle: 'Get started with ViralHook.',            button: 'Create Account' },
  forgot: { title: 'Reset password',  subtitle: "Enter your email and we'll send you a reset link.", button: 'Send Reset Link' },
}

export default function AuthScreen() {
  const { enterApp, authNotice, setAuthNotice } = useApp()
  const [mode, setMode] = useState('login') // 'login' | 'signup' | 'forgot'
  const [form, setForm] = useState({ name: '', email: '', password: '' })
  const [error, setError] = useState('')
  const [sent, setSent] = useState('')       // forgot-password confirmation
  const [loading, setLoading] = useState(false)

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const switchMode = (m) => { setMode(m); setError(''); setSent(''); setAuthNotice('') }

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    if (mode === 'signup' && form.password.length < MIN_PASSWORD) {
      setError(`Password must be at least ${MIN_PASSWORD} characters.`)
      return
    }
    setLoading(true)
    try {
      if (mode === 'forgot') {
        const res = await requestPasswordReset(form.email)
        setSent(res?.detail || 'If an account exists for this email, a reset link is on its way.')
        return
      }
      const res = mode === 'login'
        ? await loginUser({ email: form.email, password: form.password })
        : await signupUser({ name: form.name, email: form.email, password: form.password })
      setAuthNotice('')
      await enterApp(res.user)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const copy = COPY[mode]

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

        <p className="text-discord-faint text-xs">ViralHook — AI content studio for short-form creators</p>
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

          <h2 className="text-discord-white font-bold text-2xl mb-1">{copy.title}</h2>
          <p className="text-discord-muted text-sm mb-6">{copy.subtitle}</p>

          {authNotice && <Alert type="warning">{authNotice}</Alert>}
          {!USE_REAL_BACKEND && mode === 'login' && (
            <Alert type="info">
              <span className="font-semibold">Offline demo:</span> demo@viralhook.ai / demo1234
            </Alert>
          )}

          {sent ? (
            <div className="space-y-4 mt-5">
              <Alert type="success">{sent}</Alert>
              <Btn size="lg" variant="secondary" className="w-full" onClick={() => switchMode('login')}>
                Back to Sign In
              </Btn>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-4 mt-5">
              {mode === 'signup' && (
                <Input label="Full name" value={form.name} onChange={set('name')} placeholder="Alex Rivera"
                       autoComplete="name" required />
              )}
              <Input label="Email" type="email" value={form.email} onChange={set('email')} placeholder="you@example.com"
                     autoComplete="email" required />
              {mode !== 'forgot' && (
                <Input label="Password" type="password" value={form.password} onChange={set('password')}
                       placeholder={mode === 'signup' ? `At least ${MIN_PASSWORD} characters` : '••••••••'}
                       autoComplete={mode === 'signup' ? 'new-password' : 'current-password'} required />
              )}
              {mode === 'login' && (
                <button type="button" onClick={() => switchMode('forgot')}
                        className="text-discord-link text-xs hover:underline">
                  Forgot password?
                </button>
              )}

              {error && <Alert type="error">{error}</Alert>}

              <Btn type="submit" size="lg" loading={loading} className="w-full mt-2">{copy.button}</Btn>
            </form>
          )}

          <Divider label="or" />

          <button
            onClick={() => switchMode(mode === 'signup' ? 'login' : mode === 'forgot' ? 'login' : 'signup')}
            className="w-full text-center text-discord-muted text-sm hover:text-discord-white transition-colors"
          >
            {mode === 'login' ? "Don't have an account? Sign up" : 'Already have an account? Sign in'}
          </button>
        </div>
      </div>
    </div>
  )
}
