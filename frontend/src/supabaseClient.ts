import { createClient, type SupabaseClient } from '@supabase/supabase-js'

let singleton: SupabaseClient | null = null

export function isSupabaseConfigured(): boolean {
  const url = import.meta.env.VITE_SUPABASE_URL?.trim()
  const key = import.meta.env.VITE_SUPABASE_ANON_KEY?.trim()
  return Boolean(url && key)
}

/** Null when env vars are missing — UI should degrade gracefully. */
export function getSupabase(): SupabaseClient | null {
  if (!isSupabaseConfigured()) return null
  if (!singleton) {
    singleton = createClient(
      import.meta.env.VITE_SUPABASE_URL!.trim(),
      import.meta.env.VITE_SUPABASE_ANON_KEY!.trim(),
      {
        auth: {
          persistSession: true,
          autoRefreshToken: true,
          detectSessionInUrl: true,
        },
      },
    )
  }
  return singleton
}
