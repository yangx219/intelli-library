import { useEffect, useMemo, useRef, useState } from 'react'
import { gutenbergCoverCandidateUrls } from './api'
import { fetchOpenLibraryCoverUrl, isOpenLibraryCoverUrl } from './openLibraryCover'

function titleInitials(title: string | null | undefined): string {
  const t = (title ?? '').trim()
  if (!t) return '…'
  const parts = t
    .replace(/^[^\p{L}\p{N}]+/u, '')
    .split(/\s+/)
    .filter(Boolean)
  if (parts.length >= 2) {
    const a = parts[0][0] ?? ''
    const b = parts[1][0] ?? ''
    return (a + b).toUpperCase() || '…'
  }
  const word = parts[0] ?? t
  return word.slice(0, 2).toUpperCase() || '…'
}

type Props = {
  bookId: number
  coverUrl?: string | null
  title?: string | null
  authors?: string[] | null
  frameClassName: string
  imgClassName: string
  loading?: 'lazy' | 'eager'
  /** PG auto-covers load successfully but look identical; try Open Library first when no OL URL yet. */
  preferOpenLibrary?: boolean
}

export function BookCoverThumb({
  bookId,
  coverUrl,
  title,
  authors,
  frameClassName,
  imgClassName,
  loading = 'lazy',
  preferOpenLibrary = false,
}: Props) {
  const pgUrls = useMemo(() => gutenbergCoverCandidateUrls(bookId, coverUrl), [bookId, coverUrl])
  const pgKey = pgUrls.join('|')
  const authorFirst = authors?.[0]

  const [idx, setIdx] = useState(0)
  const [olUrl, setOlUrl] = useState<string | null>(null)
  const [fallback, setFallback] = useState(false)
  const [olPending, setOlPending] = useState(false)
  const olStarted = useRef(false)

  useEffect(() => {
    setIdx(0)
    setOlUrl(null)
    setFallback(false)
    setOlPending(false)
    olStarted.current = false

    const wantPrefetch =
      preferOpenLibrary && Boolean(title?.trim()) && !isOpenLibraryCoverUrl(coverUrl)
    if (!wantPrefetch) return

    olStarted.current = true
    setOlPending(true)
    void fetchOpenLibraryCoverUrl(title!, authorFirst).then((u) => {
      setOlPending(false)
      if (u) setOlUrl(u)
    })
  }, [bookId, pgKey, preferOpenLibrary, title, authorFirst, coverUrl])

  /** OL must come first when present — previously we appended OL after PG, so idx 0 still loaded PG templates. */
  const urls = useMemo(() => {
    if (!olUrl) return pgUrls
    const seen = new Set<string>([olUrl])
    return [olUrl, ...pgUrls.filter((u) => !seen.has(u))]
  }, [olUrl, pgUrls])
  const current = !fallback && !olPending && idx < urls.length ? urls[idx] : null

  const onImgError = () => {
    if (idx + 1 < urls.length) {
      setIdx((i) => i + 1)
      return
    }
    if (!olStarted.current && title?.trim()) {
      olStarted.current = true
      setOlPending(true)
      void fetchOpenLibraryCoverUrl(title, authors?.[0]).then((u) => {
        setOlPending(false)
        if (u) {
          setOlUrl(u)
          setIdx(0)
        } else {
          setFallback(true)
        }
      })
      return
    }
    setFallback(true)
  }

  return (
    <div className={frameClassName}>
      {current ? (
        <img
          key={current}
          src={current}
          alt=""
          className={imgClassName}
          loading={loading}
          decoding="async"
          referrerPolicy="no-referrer"
          onError={onImgError}
        />
      ) : olPending ? (
        <div className="book-cover-fallback book-cover-fallback-pending" aria-hidden />
      ) : (
        <div className="book-cover-fallback" aria-hidden>
          <span className="book-cover-initials">{titleInitials(title)}</span>
        </div>
      )}
    </div>
  )
}
