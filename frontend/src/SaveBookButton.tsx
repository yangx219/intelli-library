type Props = {
  saved: boolean
  busy?: boolean
  compact?: boolean
  className?: string
  onClick: () => void
}

function BookmarkGlyph({ filled }: { filled: boolean }) {
  return (
    <svg className="save-book-icon" width="15" height="15" viewBox="0 0 24 24" aria-hidden>
      {filled ? (
        <path
          fill="currentColor"
          d="M18 2H6c-1.1 0-2 .9-2 2v18l8-4.5 8 4.5V4c0-1.1-.9-2-2-2z"
        />
      ) : (
        <path
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinejoin="round"
          d="M18 4v16l-6-3.5L6 20V4a2 2 0 012-2h8a2 2 0 012 2z"
        />
      )}
    </svg>
  )
}

export function SaveBookButton({ saved, busy, compact, className = '', onClick }: Props) {
  const extra = className.trim()
  const label = busy ? '…' : saved ? 'Saved' : 'Save'

  return (
    <button
      type="button"
      className={[`save-book-btn`, saved ? 'is-saved' : '', compact ? 'is-compact' : '', extra].filter(Boolean).join(' ')}
      disabled={busy}
      onClick={onClick}
      aria-label={busy ? 'Saving' : saved ? 'Remove from saved titles' : 'Save this title'}
    >
      <span className="save-book-inner">
        {!busy && <BookmarkGlyph filled={saved} />}
        <span className="save-book-label">{label}</span>
      </span>
    </button>
  )
}
