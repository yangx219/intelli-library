import { useState, type FormEvent } from 'react'
import type { User } from '@supabase/supabase-js'
import { getSupabase, isSupabaseConfigured } from './supabaseClient'
import { useAuthSession } from './AuthSession'

function pickMetaString(meta: User['user_metadata'], keys: string[]): string {
  if (!meta || typeof meta !== 'object') return ''
  for (const k of keys) {
    const v = (meta as Record<string, unknown>)[k]
    if (typeof v === 'string' && v.trim()) return v.trim()
  }
  return ''
}

/** Chip / header label: metadata nickname or display name only — never email or phone. */
export function accountDisplayNickname(user: User | null | undefined): string {
  if (!user) return ''
  return pickMetaString(user.user_metadata, [
    'nickname',
    'preferred_username',
    'user_name',
    'username',
    'name',
    'full_name',
    'given_name',
  ])
}

/** One-letter avatar fallback (email local part or phone); does not expose full email in UI. */
function accountChipInitial(user: User): string {
  const mail = user.email?.trim()
  if (mail) {
    const local = (mail.split('@')[0] ?? mail).trim()
    for (const ch of local) {
      if (/\p{L}/u.test(ch)) return ch.toLocaleUpperCase()
      if (/\d/u.test(ch)) return ch
    }
  }
  const digits = user.phone?.replace(/\D/g, '') ?? ''
  if (digits) return digits.charAt(0)
  return '?'
}

function truncateChipLabel(text: string, max = 28): string {
  if (text.length <= max) return text
  return `${text.slice(0, Math.max(1, max - 1))}…`
}

type AuthMethod = 'magic' | 'password'
type PasswordFlow = 'signin' | 'signup'

type Props = {
  /** Opens full profile modal (parent handles overlay). */
  onOpenProfile?: () => void
}

export function SupabaseAuthChip({ onOpenProfile }: Props) {
  const configured = isSupabaseConfigured()
  const { session, ready } = useAuthSession()
  const [open, setOpen] = useState(false)
  const [authMethod, setAuthMethod] = useState<AuthMethod>('magic')
  const [pwFlow, setPwFlow] = useState<PasswordFlow>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [password2, setPassword2] = useState('')
  const [busy, setBusy] = useState(false)
  const [hint, setHint] = useState<string | null>(null)

  const redirectUrl = () => `${window.location.origin}${window.location.pathname}`

  const onMagicLink = async (e: FormEvent) => {
    e.preventDefault()
    const sb = getSupabase()
    if (!sb) return
    const trimmed = email.trim()
    if (!trimmed) {
      setHint('Enter your email address.')
      return
    }
    setBusy(true)
    setHint(null)
    try {
      const { error } = await sb.auth.signInWithOtp({
        email: trimmed,
        options: { emailRedirectTo: redirectUrl() },
      })
      if (error) setHint(error.message)
      else setHint('Magic link sent — check your inbox (and spam).')
    } finally {
      setBusy(false)
    }
  }

  const onPasswordSubmit = async (e: FormEvent) => {
    e.preventDefault()
    const sb = getSupabase()
    if (!sb) return
    const trimmedEmail = email.trim()
    if (!trimmedEmail || !password) {
      setHint('Enter email and password.')
      return
    }
    if (password.length < 6) {
      setHint('Password must be at least 6 characters.')
      return
    }
    if (pwFlow === 'signup') {
      if (password !== password2) {
        setHint('Passwords do not match.')
        return
      }
    }

    setBusy(true)
    setHint(null)
    try {
      if (pwFlow === 'signin') {
        const { error } = await sb.auth.signInWithPassword({ email: trimmedEmail, password })
        if (error) setHint(error.message)
        else {
          setHint('Signed in.')
          setOpen(false)
          setPassword('')
          setPassword2('')
        }
      } else {
        const { error } = await sb.auth.signUp({
          email: trimmedEmail,
          password,
          options: { emailRedirectTo: redirectUrl() },
        })
        if (error) setHint(error.message)
        else
          setHint(
            'Account created. If email confirmation is enabled in Supabase, check your inbox before signing in.',
          )
      }
    } finally {
      setBusy(false)
    }
  }

  const onSignOut = async () => {
    const sb = getSupabase()
    if (!sb) return
    setBusy(true)
    setHint(null)
    try {
      await sb.auth.signOut()
      setOpen(false)
    } catch (err) {
      setHint(err instanceof Error ? err.message : 'Sign-out failed.')
    } finally {
      setBusy(false)
    }
  }

  const chipNickname =
    session?.user != null ? accountDisplayNickname(session.user) : ''

  const nickTrimmed = chipNickname.trim()
  const chipTitle = nickTrimmed ? nickTrimmed : session?.user != null ? 'Signed in' : undefined

  let label: string
  if (!configured) {
    label = 'Account · pending setup'
  } else if (!ready) {
    label = 'Loading…'
  } else if (session?.user == null) {
    label = 'Account'
  } else if (nickTrimmed) {
    label = truncateChipLabel(nickTrimmed)
  } else {
    label = ''
  }

  const showInitialAvatar = configured && ready && session?.user != null && !nickTrimmed

  const chipInitial = session?.user != null ? accountChipInitial(session.user) : ''

  return (
    <div className={`auth-chip-wrap ${open ? 'is-open' : ''}`}>
      <button
        type="button"
        className={`auth-chip-trigger ${configured ? '' : 'is-muted'} ${session ? 'is-signed-in' : ''} ${showInitialAvatar ? 'auth-chip-trigger--avatar' : ''}`}
        aria-expanded={open}
        aria-label={showInitialAvatar ? 'Account menu, signed in' : undefined}
        title={chipTitle}
        onClick={() => setOpen((v) => !v)}
      >
        {showInitialAvatar ? (
          <span className="auth-chip-avatar" aria-hidden>
            {chipInitial}
          </span>
        ) : (
          label
        )}
      </button>
      {open && (
        <div className="auth-chip-panel" role="dialog" aria-label="Account">
          {!configured ? (
            <>
              <p className="auth-chip-lead">Cross-device bookmarks aren&apos;t enabled on this deployment yet.</p>
              <p className="auth-chip-muted">
                Your Intelli Library administrator connects reader accounts (Supabase) by adding{' '}
                <code className="auth-chip-code">VITE_SUPABASE_URL</code> and{' '}
                <code className="auth-chip-code">VITE_SUPABASE_ANON_KEY</code> to the hosted web configuration, then
                redeploying the interface.
              </p>
              <pre className="auth-chip-pre">
                {`VITE_SUPABASE_URL=https://….supabase.co\nVITE_SUPABASE_ANON_KEY=…`}
              </pre>
              <p className="auth-chip-muted">Never commit production secrets to source control.</p>
              <p className="auth-chip-muted">
                Apply <code className="auth-chip-code">supabase/sql/saved_books.sql</code> in your Supabase SQL editor,
                then enable email / password auth for readers.
              </p>
            </>
          ) : session ? (
            <>
              {(() => {
                const nick = accountDisplayNickname(session.user).trim()
                return <p className="auth-chip-lead">{nick || 'Signed in'}</p>
              })()}
              <div className="auth-chip-signed-actions">
                {onOpenProfile && (
                  <button
                    type="button"
                    className="auth-chip-submit auth-chip-submit-outline"
                    disabled={busy}
                    onClick={() => {
                      onOpenProfile()
                      setOpen(false)
                    }}
                  >
                    Profile & saved
                  </button>
                )}
                <button type="button" className="auth-chip-btn-secondary" disabled={busy} onClick={() => void onSignOut()}>
                  Sign out
                </button>
              </div>
            </>
          ) : (
            <>
              <div className="auth-chip-tabs" role="tablist" aria-label="Sign-in method">
                <button
                  type="button"
                  role="tab"
                  aria-selected={authMethod === 'magic'}
                  className={`auth-chip-tab ${authMethod === 'magic' ? 'is-active' : ''}`}
                  onClick={() => {
                    setAuthMethod('magic')
                    setHint(null)
                  }}
                >
                  Magic link
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={authMethod === 'password'}
                  className={`auth-chip-tab ${authMethod === 'password' ? 'is-active' : ''}`}
                  onClick={() => {
                    setAuthMethod('password')
                    setHint(null)
                  }}
                >
                  Password
                </button>
              </div>

              {authMethod === 'magic' ? (
                <>
                  <p className="auth-chip-muted auth-chip-aftertabs">We email you a one-time sign-in link.</p>
                  <form className="auth-chip-form" onSubmit={(ev) => void onMagicLink(ev)}>
                    <label className="visually-hidden" htmlFor="auth-email">
                      Email
                    </label>
                    <input
                      id="auth-email"
                      type="email"
                      autoComplete="email"
                      className="auth-chip-input"
                      placeholder="you@example.com"
                      value={email}
                      onChange={(ev) => setEmail(ev.target.value)}
                      disabled={busy}
                    />
                    <button type="submit" className="auth-chip-submit" disabled={busy}>
                      {busy ? 'Sending…' : 'Send link'}
                    </button>
                  </form>
                </>
              ) : (
                <>
                  <div className="auth-chip-subtabs">
                    <button
                      type="button"
                      className={`auth-chip-subtab ${pwFlow === 'signin' ? 'is-active' : ''}`}
                      onClick={() => {
                        setPwFlow('signin')
                        setHint(null)
                      }}
                    >
                      Sign in
                    </button>
                    <button
                      type="button"
                      className={`auth-chip-subtab ${pwFlow === 'signup' ? 'is-active' : ''}`}
                      onClick={() => {
                        setPwFlow('signup')
                        setHint(null)
                      }}
                    >
                      Create account
                    </button>
                  </div>
                  <form className="auth-chip-form auth-chip-form-stack" onSubmit={(ev) => void onPasswordSubmit(ev)}>
                    <label className="visually-hidden" htmlFor="auth-email-pw">
                      Email
                    </label>
                    <input
                      id="auth-email-pw"
                      type="email"
                      autoComplete="email"
                      className="auth-chip-input"
                      placeholder="you@example.com"
                      value={email}
                      onChange={(ev) => setEmail(ev.target.value)}
                      disabled={busy}
                    />
                    <label className="visually-hidden" htmlFor="auth-password">
                      Password
                    </label>
                    <input
                      id="auth-password"
                      type="password"
                      autoComplete={pwFlow === 'signup' ? 'new-password' : 'current-password'}
                      className="auth-chip-input"
                      placeholder="Password (min. 6 characters)"
                      value={password}
                      onChange={(ev) => setPassword(ev.target.value)}
                      disabled={busy}
                    />
                    {pwFlow === 'signup' && (
                      <>
                        <label className="visually-hidden" htmlFor="auth-password2">
                          Confirm password
                        </label>
                        <input
                          id="auth-password2"
                          type="password"
                          autoComplete="new-password"
                          className="auth-chip-input"
                          placeholder="Confirm password"
                          value={password2}
                          onChange={(ev) => setPassword2(ev.target.value)}
                          disabled={busy}
                        />
                      </>
                    )}
                    <button type="submit" className="auth-chip-submit" disabled={busy}>
                      {busy ? 'Working…' : pwFlow === 'signin' ? 'Sign in' : 'Create account'}
                    </button>
                  </form>
                </>
              )}
            </>
          )}
          {hint && (
            <p
              className={`auth-chip-hint ${hint.includes('sent') || hint.includes('Signed in') || hint.includes('Account created') ? 'is-ok' : ''}`}
            >
              {hint}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
