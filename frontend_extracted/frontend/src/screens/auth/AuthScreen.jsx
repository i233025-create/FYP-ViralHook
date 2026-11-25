import { useState } from 'react'
import { ArrowRight } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { USE_REAL_BACKEND, loginUser, signupUser, requestPasswordReset } from '../../services/api'
import { Btn, Input, Alert } from '../../components/ui'
import AuthFrame, { AuthTitle } from './AuthFrame'

const MIN_PASSWORD = 8

const COPY = {
  login:  { title: ['Sign', 'in'],         subtitle: 'Welcome back. Continue where you left off.', button: 'Sign in' },
  signup: { title: ['Create', 'account'],  subtitle: 'Your scripts and videos, in your own voice.',  button: 'Create account' },
  forgot: { title: ['Reset', 'password'],  subtitle: "Enter your email and we'll send you a link to choose a new password.", button: 'Send reset link' },
}

export default function AuthScreen({ initialMode = 'login' }) {
  const { enterApp, authNotice, setAuthNotice } = useApp()
  const [mode, setMode] = useState(initialMode) // 'login' | 'signup' | 'forgot'
  const [form, setForm] = useState({ name: '', email: '', password: '' })
  const [error, setError] = useState('')
  const [sent, setSent] = useState('')
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
    <AuthFrame
      chip={mode === 'signup' ? 'New account' : mode === 'forgot' ? 'Password' : 'Welcome back'}
      headerRight={<>
        <span className="hidden text-vh-cream sm:inline">
          {mode === 'signup' ? 'Already have an account?' : 'New to ViralHook?'}
        </span>
        <Btn variant="secondary" size="sm" onClick={() => switchMode(mode === 'signup' ? 'login' : 'signup')}>
          {mode === 'signup' ? 'Sign in' : 'Create account'}
        </Btn>
      </>}
    >
      <div className="rounded-2xl border-2 border-vh-night bg-white p-6 shadow-hard sm:p-8">
        <AuthTitle plain={copy.title[0]} highlight={copy.title[1]} sub={copy.subtitle} />

        <div className="space-y-3">
          {authNotice && <Alert type="warning">{authNotice}</Alert>}
          {!USE_REAL_BACKEND && mode === 'login' && (
            <Alert type="info" chip="Demo">Offline demo — sign in with demo@viralhook.ai / demo1234</Alert>
          )}
        </div>

        {sent ? (
          <div className="mt-6 space-y-5">
            <Alert type="success">{sent}</Alert>
            <Btn variant="secondary" size="md" className="w-full" onClick={() => switchMode('login')}>Back to sign in</Btn>
          </div>
        ) : (
          <form onSubmit={submit} className="mt-5 space-y-4">
            {mode === 'signup' && (
              <Input label="Full name" value={form.name} onChange={set('name')} placeholder="Hamza Bhatti"
                autoComplete="name" required />
            )}
            <Input label="Email" type="email" value={form.email} onChange={set('email')} placeholder="you@example.com"
              autoComplete="email" required />
            {mode !== 'forgot' && (
              <div>
                <Input label="Password" type="password" value={form.password} onChange={set('password')}
                  placeholder={mode === 'signup' ? `At least ${MIN_PASSWORD} characters` : ''}
                  autoComplete={mode === 'signup' ? 'new-password' : 'current-password'} required />
                {mode === 'login' && (
                  <div className="mt-2 text-right">
                    <button type="button" onClick={() => switchMode('forgot')}
                      className="text-[14px] font-semibold underline underline-offset-4 hover:text-vh-accent2">
                      Forgot password?
                    </button>
                  </div>
                )}
              </div>
            )}

            {error && <Alert type="error">{error}</Alert>}

            <Btn type="submit" size="lg" loading={loading} iconRight={ArrowRight} className="mt-2 w-full">{copy.button}</Btn>
          </form>
        )}

        <p className="mt-6 text-center text-[15px]">
          {mode === 'login' ? 'New to ViralHook? ' : mode === 'signup' ? 'Already have an account? ' : 'Remembered it? '}
          <button type="button" onClick={() => switchMode(mode === 'login' ? 'signup' : 'login')}
            className="font-bold underline underline-offset-4 hover:text-vh-accent2">
            {mode === 'login' ? 'Create an account' : 'Sign in'}
          </button>
        </p>
      </div>
    </AuthFrame>
  )
}
