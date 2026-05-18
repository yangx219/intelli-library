import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { Session } from '@supabase/supabase-js'
import { getSupabase, isSupabaseConfigured } from './supabaseClient'

type AuthCtx = {
  session: Session | null
  /** False until first getSession resolves (or Supabase missing). */
  ready: boolean
}

const Ctx = createContext<AuthCtx>({ session: null, ready: false })

export function AuthSessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [ready, setReady] = useState(!isSupabaseConfigured())

  useEffect(() => {
    const sb = getSupabase()
    if (!sb) {
      setSession(null)
      setReady(true)
      return
    }

    let cancelled = false
    void sb.auth.getSession().then(({ data }) => {
      if (cancelled) return
      setSession(data.session ?? null)
      setReady(true)
    })

    const { data: sub } = sb.auth.onAuthStateChange((_event, next) => {
      setSession(next)
    })

    return () => {
      cancelled = true
      sub.subscription.unsubscribe()
    }
  }, [])

  const value = useMemo(() => ({ session, ready }), [session, ready])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useAuthSession(): AuthCtx {
  return useContext(Ctx)
}
