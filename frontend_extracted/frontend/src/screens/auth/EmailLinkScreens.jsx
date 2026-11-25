import { useEffect, useRef, useState } from 'react'
import { MailCheck, KeyRound } from 'lucide-react'
import { LogoMark } from '../../components/brand/Logo'
import AuthFrame, { AuthTitle } from './AuthFrame'
import { useApp } from '../../context/AppContext'
import { getCurrentUser, resetPassword, verifyEmail } from '../../services/api'
import { Btn, Input, Alert, Spinner } from '../../components/ui'

// Screens opened from email links (/verify-email?token=… and /reset-password?token=…).

const MIN_PASSWORD = 8

/** Drop the token from the address bar once it has been used. */
function clearLinkFromUrl() {
  window.history.replaceState(null, '', '/')
}

function Shell({ icon: Icon, title, chip, children }) {
  return (
    <AuthFrame chip={chip}>
      <div className="rounded-2xl border-2 border-vh-night bg-white p-6 shadow-hard sm:p-8">
        <span className="mb-5 flex h-14 w-14 items-center justify-center rounded-xl border-2 border-vh-night bg-vh-accent">
          <Icon size={26} strokeWidth={2} />
        </span>
        <AuthTitle plain={title[0]} highlight={title[1]} />
        <div className="space-y-4">{children}</div>
      </div>
    </AuthFrame>
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
    <Shell icon={MailCheck} title={['Verify', 'email']} chip="Email link">
      {state === 'working' && <p className="flex items-center gap-2 text-[16px] font-medium"><Spinner size={18} /> Checking your link…</p>}
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
    <Shell icon={KeyRound} title={['New', 'password']} chip="Email link">
      <p className="text-[16px] leading-relaxed">
        After saving, every device signed in to your account is signed out.
      </p>
      <form onSubmit={submit} className="space-y-4">
        <Input label="New password" type="password" value={password} autoComplete="new-password"
               onChange={(e) => setPassword(e.target.value)} placeholder={`At least ${MIN_PASSWORD} characters`} required />
        <Input label="Repeat new password" type="password" value={confirm} autoComplete="new-password"
               onChange={(e) => setConfirm(e.target.value)} required />
        {error && <Alert type="error">{error}</Alert>}
        <Btn type="submit" size="lg" loading={loading} className="w-full">Save password</Btn>
      </form>
      <button onClick={() => { clearLinkFromUrl(); navigate('auth') }}
              className="w-full text-center text-[15px] font-bold underline underline-offset-4 hover:text-vh-accent2">
        Back to sign in
      </button>
    </Shell>
  )
}

export function BootScreen() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 px-6" role="status" aria-live="polite">
      <div className="on-dark w-full max-w-sm overflow-hidden rounded-2xl bg-vh-night shadow-accent">
        <div className="clapper h-9" aria-hidden="true" />
        <div className="flex flex-col items-center px-8 pb-8 pt-7">
          <LogoMark className="h-16 w-auto animate-pulse text-vh-accent" />
          <p className="display mt-5 text-[2.4rem] text-vh-cream">Loading your <span className="text-vh-accent">studio</span></p>
          <div className="mt-5 h-[9px] w-full animate-strip sprockets" aria-hidden="true" />
        </div>
      </div>
    </div>
  )
}
