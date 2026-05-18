import type { Session } from '@supabase/supabase-js'
import { useEffect, useMemo, useState } from 'react'
import { BookCoverThumb } from './BookCoverThumb'
import { getSupabase } from './supabaseClient'
import type { SavedBookRow } from './savedBooksDb'

type Props = {
  open: boolean
  onClose: () => void
  session: Session
  savedList: SavedBookRow[]
  savingId: number | null
  onToggleSaved: (bookId: number, title: string) => void
}

type ProfileTab = 'overview' | 'saved' | 'ai'

function formatJoined(iso: string | undefined): string {
  if (!iso) return '—'
  try {
    return new Intl.DateTimeFormat('en', { dateStyle: 'medium' }).format(new Date(iso))
  } catch {
    return iso
  }
}

export function UserProfileModal({
  open,
  onClose,
  session,
  savedList,
  savingId,
  onToggleSaved,
}: Props) {
  const [tab, setTab] = useState<ProfileTab>('overview')
  const [savedFilter, setSavedFilter] = useState('')

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = prevOverflow
    }
  }, [open, onClose])

  useEffect(() => {
    if (open) {
      setTab('overview')
      setSavedFilter('')
    }
  }, [open])

  const filteredSaved = useMemo(() => {
    const q = savedFilter.trim().toLowerCase()
    if (!q) return savedList
    return savedList.filter((row) => {
      const t = (row.title ?? '').toLowerCase()
      return t.includes(q) || String(row.book_id).includes(q)
    })
  }, [savedList, savedFilter])

  const email = session.user.email ?? '—'
  const created = formatJoined(session.user.created_at)
  const initial = email.charAt(0).toUpperCase()

  const signOut = async () => {
    const sb = getSupabase()
    if (sb) await sb.auth.signOut()
    onClose()
  }

  if (!open) return null

  return (
    <div className="profile-modal-root" role="dialog" aria-modal="true" aria-labelledby="profile-heading">
      <button type="button" className="profile-modal-backdrop" aria-label="Close dialog" onClick={onClose} />
      <div className="profile-modal-card">
        <div className="profile-modal-head">
          <h2 id="profile-heading" className="profile-modal-title">
            Account
          </h2>
          <button type="button" className="profile-modal-close" aria-label="Close" onClick={onClose}>
            ×
          </button>
        </div>

        <div className="profile-modal-tabs" role="tablist" aria-label="Account sections">
          {(
            [
              ['overview', 'Overview'],
              ['saved', `Saved (${savedList.length})`],
              ['ai', 'Reading help'],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              className={`profile-modal-tab ${tab === id ? 'is-active' : ''}`}
              onClick={() => setTab(id)}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="profile-modal-body">
          {tab === 'overview' && (
            <div className="profile-overview">
              <div className="profile-overview-hero">
                <div className="profile-avatar" aria-hidden>
                  {initial}
                </div>
                <div className="profile-overview-text">
                  <p className="profile-overview-email">{email}</p>
                  <p className="profile-overview-meta">Member since {created}</p>
                </div>
              </div>
              <div className="profile-stat-cards">
                <button type="button" className="profile-stat-card" onClick={() => setTab('saved')}>
                  <span className="profile-stat-value">{savedList.length}</span>
                  <span className="profile-stat-label">Saved titles</span>
                  <span className="profile-stat-hint">Manage list →</span>
                </button>
                <button type="button" className="profile-stat-card profile-stat-card-muted" onClick={() => setTab('ai')}>
                  <span className="profile-stat-value">AI</span>
                  <span className="profile-stat-label">Reading help</span>
                  <span className="profile-stat-hint">How it works →</span>
                </button>
              </div>
            </div>
          )}

          {tab === 'saved' && (
            <div className="profile-saved-panel">
              <label className="profile-filter-label" htmlFor="saved-filter">
                Filter saved
              </label>
              <input
                id="saved-filter"
                type="search"
                className="profile-filter-input"
                placeholder="Title or Gutenberg ID…"
                value={savedFilter}
                onChange={(e) => setSavedFilter(e.target.value)}
                autoComplete="off"
              />
              {filteredSaved.length === 0 ? (
                <p className="profile-modal-muted profile-empty">
                  {savedList.length === 0
                    ? 'Nothing saved yet — run a search and tap Save on titles you like.'
                    : 'No matches — try another filter.'}
                </p>
              ) : (
                <ul className="profile-modal-saved-ul">
                  {filteredSaved.map((row) => (
                    <li key={row.book_id} className="profile-modal-saved-row">
                      <BookCoverThumb
                        bookId={row.book_id}
                        title={row.title}
                        authors={undefined}
                        preferOpenLibrary
                        frameClassName="hit-cover-frame profile-saved-cover-frame"
                        imgClassName="hit-cover-img"
                      />
                      <div className="profile-saved-main">
                        <a
                          className="profile-modal-saved-link"
                          href={`https://www.gutenberg.org/ebooks/${row.book_id}`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {row.title?.trim() || `Book ${row.book_id}`}
                        </a>
                        <span className="profile-saved-id">PG #{row.book_id}</span>
                      </div>
                      <button
                        type="button"
                        className="profile-modal-remove"
                        title="Remove from saved"
                        disabled={savingId === row.book_id}
                        onClick={() => onToggleSaved(row.book_id, row.title ?? '')}
                      >
                        Remove
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {tab === 'ai' && (
            <div className="profile-ai-panel">
              <div className="profile-ai-card">
                <h3 className="profile-ai-card-title">Quick guide</h3>
                <p className="profile-ai-lead">
                  <strong>Reading companion</strong> is the panel on the right. After you search, you can ask for a short
                  thematic note or chat about what showed up — like a shelf-side helper, not a replacement for reading the
                  texts themselves.
                </p>
                <ul className="profile-ai-tips">
                  <li>
                    Tap <strong>Generate reading brief</strong> for a compact overview of your current results, or scroll
                    to <strong>Research concierge</strong> and type follow-ups in everyday language.
                  </li>
                  <li>
                    The concierge thread stays on <strong>this device only</strong>. Starting a new topic? Tap{' '}
                    <strong>Clear conversation</strong> first so answers don&apos;t mix with an older chat.
                  </li>
                  <li>
                    If a brief or reply never finishes loading, reading help might not be turned on where you&apos;re
                    browsing — try again later, or use this site&apos;s usual contact or feedback option.
                  </li>
                </ul>
                <p className="profile-ai-foot">
                  When you need exact wording, titles, or citations, open the books from your results — treat AI replies as
                  orientation only.
                </p>
              </div>
            </div>
          )}
        </div>

        <div className="profile-modal-footer">
          <button type="button" className="profile-modal-btn-signout" onClick={() => void signOut()}>
            Sign out
          </button>
        </div>
      </div>
    </div>
  )
}
