import { useEffect, useRef, useState } from 'react'
import { Zap, MailCheck, KeyRound } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { getCurrentUser, resetPassword, verifyEmail } from '../../services/api'
import { Btn, Input, Alert } from '../../components/ui'

// Screens opened from email links (/verify-email?token=… and /reset-password?token=…).

const MIN_PASSWORD = 8

/** Drop the token from the address bar once it has been used. */
function clearLinkFromUrl() {
  window.history.replaceState(null, '', '/')
}

function Shell({ icon: Icon, title, children }) {
  return (
    <div className="flex h-screen w-screen items-center justify-center bg-discord-dark p-6">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-2 mb-8">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-discord-blurple">
            <Zap size={16} className="text-white" />
          </div>
          <span className="text-discord-white font-bold">ViralHook</span>
        </div>
        <div className="flex items-center gap-3 mb-5">
          <Icon size={22} className="text-discord-blurple" />
          <h2 className="text-discord-white font-bold text-2xl">{title}</h2>
        </div>
        <div className="space-y-4">{children}</div>
      </div>
    </div>
  )
}

export function VerifyEmailScreen() {
  const { linkToken, enterApp, navigate, setUser } = useApp()
  const [state, setState] = useState('working') // working | done | failed
  const [message, setMessage] = useState('')
  const started = useRef(false)

  useEffect(() => {
    if (started.current) return   // React StrictMode runs effects twice; a link works once
    started.current = true
    verifyEmail(linkToken)
      .then(({ user }) => { setUser(user); setState('done') })
      .catch((err) => { setMessage(err.message); setState('failed') })
      .finally(clearLinkFromUrl)
  }, [linkToken, setUser])

  const proceed = async () => {
    const user = await getCurrentUser().catch(() => null)
    if (user) await enterApp(user)
    else navigate('auth')
  }

  return (
    <Shell icon={MailCheck} title="Verify email">
      {state === 'working' && <p className="text-discord-muted text-sm">Checking your link…</p>}
      {state === 'done' && <Alert type="success">Your email is verified. Thank you!</Alert>}
      {state === 'failed' && (
        <Alert type="error">
          {message} You can ask for a new link from the banner after signing in.
        </Alert>
      )}
      {state !== 'working' && <Btn size="lg" className="w-full" onClick={proceed}>Continue</Btn>}
    </Shell>
  )
}

export function ResetPasswordScreen() {
  const { linkToken, navigate, setAuthNotice } = useApp()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    if (password.length < MIN_PASSWORD) return setError(`Password must be at least ${MIN_PASSWORD} characters.`)
    if (password !== confirm) return setError("The two passwords don't match.")
    setLoading(true)
    try {
      await resetPassword(linkToken, password)
      clearLinkFromUrl()
      setAuthNotice('Password changed. Sign in with your new password.')
      navigate('auth')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Shell icon={KeyRound} title="Choose a new password">
      <p className="text-discord-muted text-sm">
        After saving, every device signed in to your account is signed out.
      </p>
      <form onSubmit={submit} className="space-y-4">
        <Input label="New password" type="password" value={password} autoComplete="new-password"
               onChange={(e) => setPassword(e.target.value)} placeholder={`At least ${MIN_PASSWORD} characters`} required />
        <Input label="Repeat new password" type="password" value={confirm} autoComplete="new-password"
               onChange={(e) => setConfirm(e.target.value)} required />
        {error && <Alert type="error">{error}</Alert>}
        <Btn type="submit" size="lg" loading={loading} className="w-full">Save Password</Btn>
      </form>
      <button onClick={() => { clearLinkFromUrl(); navigate('auth') }}
              className="w-full text-center text-discord-muted text-sm hover:text-discord-white">
        Back to Sign In
      </button>
    </Shell>
  )
}

export function BootScreen() {
  return (
    <div className="flex h-screen w-screen items-center justify-center bg-discord-dark">
      <div className="flex items-center gap-3 text-discord-muted text-sm">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-discord-blurple animate-pulse">
          <Zap size={16} className="text-white" />
        </div>
        Loading your workspace…
      </div>
    </div>
  )
}
