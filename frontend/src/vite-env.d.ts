/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_SUPABASE_URL?: string
  readonly VITE_SUPABASE_ANON_KEY?: string
  /** Django API origin when frontend is on another domain (no trailing slash). */
  readonly VITE_API_BASE?: string
}
