import type { Session } from '@supabase/supabase-js'
import { getSupabase } from './supabaseClient'

const TABLE = 'saved_books'

export interface SavedBookRow {
  book_id: number
  title: string | null
  created_at: string
}

export async function listSavedBooks(): Promise<SavedBookRow[]> {
  const sb = getSupabase()
  if (!sb) return []
  const {
    data: { user },
  } = await sb.auth.getUser()
  if (!user) return []
  const { data, error } = await sb
    .from(TABLE)
    .select('book_id, title, created_at')
    .order('created_at', { ascending: false })
  if (error) throw error
  return (data ?? []) as SavedBookRow[]
}

export async function saveBook(session: Session, bookId: number, title: string): Promise<void> {
  const sb = getSupabase()
  if (!sb) throw new Error('Supabase is not configured.')
  const uid = session.user.id
  const trimmedTitle = title.trim().slice(0, 800)
  const { error } = await sb.from(TABLE).upsert(
    {
      user_id: uid,
      book_id: bookId,
      title: trimmedTitle || null,
    },
    { onConflict: 'user_id,book_id' },
  )
  if (error) throw error
}

export async function unsaveBook(session: Session, bookId: number): Promise<void> {
  const sb = getSupabase()
  if (!sb) throw new Error('Supabase is not configured.')
  const { error } = await sb.from(TABLE).delete().eq('user_id', session.user.id).eq('book_id', bookId)
  if (error) throw error
}
