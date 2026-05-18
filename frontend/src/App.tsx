import { useCallback, useEffect, useId, useState, type FormEvent } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  fetchAiChat,
  fetchAiExplain,
  fetchIndexStats,
  fetchClassicBooks,
  fetchRecommendations,
  fetchSearch,
  type ChatMessage,
  type IndexStats,
  type PopularBook,
  type RankingOrder,
  type RecommendItem,
  type SearchHit,
  type SearchMode,
} from './api'
import './App.css'
import { useAuthSession } from './AuthSession'
import { SaveBookButton } from './SaveBookButton'
import { BookCoverThumb } from './BookCoverThumb'
import { SupabaseAuthChip } from './SupabaseAuthChip'
import { UserProfileModal } from './UserProfileModal'
import { isSupabaseConfigured } from './supabaseClient'
import { staticCuratedClassics } from './classicBooksFallback'
import { listSavedBooks, saveBook, unsaveBook, type SavedBookRow } from './savedBooksDb'

const MODES: { value: SearchMode; label: string; hint: string }[] = [
  { value: 'keywords', label: 'Full text', hint: 'Look inside the books themselves' },
  { value: 'title', label: 'Title', hint: 'Match titles — several words can appear separately (e.g. War Peace)' },
  { value: 'author', label: 'Author', hint: 'Look up writers and editors' },
  { value: 'regex', label: 'Pattern', hint: 'Match with a pattern (regex) — precise character-level searches' },
]

const ORDERS: { value: RankingOrder; label: string }[] = [
  { value: 'default', label: 'Best match' },
  { value: 'pagerank', label: 'Landmark titles' },
  { value: 'closeness', label: 'Well-connected works' },
  { value: 'betweenness', label: 'Cross-topic bridges' },
]

/** Quick-search chips shown above — tweak freely or replace with API-driven suggestions later. */
const STARTER_WORDS = [
  'ocean',
  'moon',
  'London',
  'captain',
  'France',
  'Hamlet',
  'ghost',
  'forest',
  'truth',
  'war',
  'castle',
  'spring',
]

const CHAT_STORAGE_KEY = 'ibe-ai-chat-v1'

function loadChatMessages(): ChatMessage[] {
  try {
    const raw = localStorage.getItem(CHAT_STORAGE_KEY)
    if (!raw) return []
    const p = JSON.parse(raw) as unknown
    if (!Array.isArray(p)) return []
    const out: ChatMessage[] = []
    for (const item of p) {
      if (!item || typeof item !== 'object') continue
      const role = (item as { role?: string }).role
      const content = (item as { content?: string }).content
      if (
        (role === 'user' || role === 'assistant') &&
        typeof content === 'string' &&
        content.trim().length > 0
      ) {
        out.push({ role, content: content.trim() })
      }
    }
    return out.slice(-40)
  } catch {
    return []
  }
}

function formatNum(n: number | null | undefined) {
  if (n == null || Number.isNaN(n)) return '—'
  return new Intl.NumberFormat('en-GB').format(n)
}

function formatAvgTokens(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return '—'
  return n.toLocaleString('en-GB', { maximumFractionDigits: 1 })
}

function formatBackendTiming(ms: number | null | undefined): string {
  if (ms == null || Number.isNaN(ms)) return '—'
  if (ms < 1000) return `${Math.round(ms)} ms`
  return `${(ms / 1000).toFixed(2)} s`
}

function displayWord(q: string) {
  return q.charAt(0).toUpperCase() + q.slice(1)
}

function parseSimilarity01(reason?: string): number | null {
  const m = reason?.match(/([\d.]+)\s*$/)
  if (!m) return null
  const v = parseFloat(m[1])
  if (Number.isNaN(v)) return null
  return Math.min(1, Math.max(0, v))
}

function LogoMark() {
  const gradId = `logo-grad-${useId().replace(/:/g, '')}`
  return (
    <svg className="logo-svg" viewBox="0 0 40 40" fill="none" aria-hidden>
      <defs>
        <linearGradient id={gradId} x1="6" y1="6" x2="36" y2="34" gradientUnits="userSpaceOnUse">
          <stop stopColor="#6b5344" />
          <stop offset="1" stopColor="#8f9b86" />
        </linearGradient>
      </defs>
      <rect width="40" height="40" rx="12" fill={`url(#${gradId})`} />
      <path d="M11 28V12l7-2v18l-7 2Zm9-1V11l9 2.2V26.8l-9 2.2Z" fill="#fffcf7" opacity={0.96} />
    </svg>
  )
}

function IconSpark() {
  return (
    <svg className="icon-spark" width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M12 2l1.2 4.2L17 7l-3.8 1.8L12 13l-1.2-4.2L7 7l3.8-1.8L12 2zM18 14l.8 2.8 2.8.8-2.8.8-.8 2.8-.8-2.8-2.8-.8 2.8-.8.8-2.8L18 14z"
        fill="currentColor"
        opacity={0.92}
      />
    </svg>
  )
}

function PopularCoverCard({
  book,
  showSave,
  saved,
  saveBusy,
  onToggleSave,
}: {
  book: PopularBook
  showSave: boolean
  saved: boolean
  saveBusy: boolean
  onToggleSave: () => void
}) {
  const authorLine = book.authors.slice(0, 2).join(', ') || 'Author unknown'

  return (
    <div className="popular-card">
      <a
        className="popular-card-main"
        href={book.gutenberg_url}
        target="_blank"
        rel="noreferrer"
        title={`Open “${book.title}” on Project Gutenberg`}
      >
        <BookCoverThumb
          bookId={book.book_id}
          coverUrl={book.cover_url}
          title={book.title}
          authors={book.authors}
          preferOpenLibrary
          frameClassName="popular-cover-frame"
          imgClassName="popular-cover-img"
        />
        <span className="popular-card-title">{book.title}</span>
        <span className="popular-card-author">{authorLine}</span>
        {book.in_local_index === false ? (
          <span className="popular-not-indexed-hint">Opens at Project Gutenberg — add this title to your library to search it here.</span>
        ) : null}
      </a>
      {showSave && (
        <div className="popular-card-save">
          <SaveBookButton
            compact
            className="popular-save-btn"
            saved={saved}
            busy={saveBusy}
            onClick={() => onToggleSave()}
          />
        </div>
      )}
    </div>
  )
}

export default function App() {
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState<SearchMode>('keywords')
  const [order, setOrder] = useState<RankingOrder>('default')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [results, setResults] = useState<SearchHit[]>([])
  const [recs, setRecs] = useState<RecommendItem[]>([])
  const [stats, setStats] = useState<IndexStats | null>(null)
  const [statsLoadState, setStatsLoadState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [aiText, setAiText] = useState<string | null>(null)
  const [aiLoading, setAiLoading] = useState(false)
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(() => loadChatMessages())
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [searchMeta, setSearchMeta] = useState<{ total: number; ms: number | null } | null>(null)
  const [insightsSnap, setInsightsSnap] = useState<{
    q: string
    mode: SearchMode
    order: RankingOrder
    hits: number
    ms: number | null
  } | null>(null)
  const [queryHint, setQueryHint] = useState<string | null>(null)
  const [classicShelfBooks, setClassicShelfBooks] = useState<PopularBook[]>([])

  const { session } = useAuthSession()
  const [savedIds, setSavedIds] = useState<Set<number>>(() => new Set())
  const [savedList, setSavedList] = useState<SavedBookRow[]>([])
  const [savingId, setSavingId] = useState<number | null>(null)
  const [profileOpen, setProfileOpen] = useState(false)

  const loadStats = useCallback(async () => {
    setStatsLoadState('loading')
    try {
      setStats(await fetchIndexStats())
      setStatsLoadState('ready')
    } catch {
      setStats(null)
      setStatsLoadState('error')
    }
  }, [])

  const loadClassicShelf = useCallback(async () => {
    try {
      const data = await fetchClassicBooks(12)
      setClassicShelfBooks(data.items.length > 0 ? data.items : staticCuratedClassics(12))
    } catch {
      setClassicShelfBooks(staticCuratedClassics(12))
    }
  }, [])

  const refreshSaved = useCallback(async () => {
    if (!session?.user?.id) {
      setSavedList([])
      setSavedIds(new Set())
      return
    }
    try {
      const rows = await listSavedBooks()
      setSavedList(rows)
      setSavedIds(new Set(rows.map((r) => r.book_id)))
    } catch {
      setSavedList([])
      setSavedIds(new Set())
    }
  }, [session?.user?.id])

  useEffect(() => {
    void loadStats()
  }, [loadStats])

  useEffect(() => {
    void loadClassicShelf()
  }, [loadClassicShelf])

  useEffect(() => {
    void refreshSaved()
  }, [refreshSaved])

  useEffect(() => {
    try {
      localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(chatMessages.slice(-40)))
    } catch {
      /* quota */
    }
  }, [chatMessages])

  const runSearch = async (e?: FormEvent, overrideQuery?: string) => {
    e?.preventDefault()
    const raw = overrideQuery !== undefined ? overrideQuery : query
    const q = raw.trim()
    setQuery(q)
    if (!q) {
      setResults([])
      setRecs([])
      setError(null)
      setSearchMeta(null)
      setInsightsSnap(null)
      setQueryHint('Enter a word or phrase above, then tap Search.')
      return
    }
    setQueryHint(null)
    setLoading(true)
    setError(null)
    setAiText(null)
    let searchOk = false
    try {
      const data = await fetchSearch(q, mode, order)
      setResults(data.results ?? [])
      const ms = data.elapsed_ms ?? null
      setSearchMeta({ total: data.results?.length ?? 0, ms })
      setInsightsSnap({ q, mode, order, hits: data.results?.length ?? 0, ms })
      searchOk = true
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
      setResults([])
      setRecs([])
      setSearchMeta(null)
      setInsightsSnap(null)
    } finally {
      setLoading(false)
    }
    if (searchOk) {
      try {
        const r = await fetchRecommendations(q, 6)
        setRecs(r.items ?? [])
      } catch {
        setRecs([])
      }
    }
  }

  const runAi = async () => {
    const q = query.trim()
    if (!q || results.length === 0) return
    setAiLoading(true)
    setAiText(null)
    try {
      const titles = results.map((r) => r.title).filter(Boolean) as string[]
      const ids = results.map((r) => r.book_id).filter((id): id is number => typeof id === 'number')
      const data = await fetchAiExplain(q, titles, ids.length > 0 ? ids : undefined)
      if (data.explanation) setAiText(data.explanation)
      else if (data.detail) setAiText(data.detail)
      else if (data.error) setAiText(`Service notice: ${data.error}`)
    } catch (err) {
      setAiText(err instanceof Error ? err.message : 'The reading companion could not respond. Please try again.')
    } finally {
      setAiLoading(false)
    }
  }

  const sendAgentChat = async () => {
    const text = chatInput.trim()
    if (!text || chatLoading) return
    setChatLoading(true)
    setChatInput('')
    const thread = [...chatMessages, { role: 'user' as const, content: text }]
    setChatMessages(thread)
    try {
      const searchContext =
        results.length > 0 && query.trim()
          ? {
              query: query.trim(),
              hits: results.slice(0, 18).map((r) => ({
                book_id: r.book_id ?? undefined,
                title: r.title ?? '',
                authors:
                  Array.isArray(r.authors) && r.authors.length > 0 ? r.authors.join(', ') : undefined,
              })),
            }
          : undefined
      const data = await fetchAiChat(thread, { searchContext })
      const reply =
        (data.reply && data.reply.trim()) ||
        data.detail ||
        (data.error ? `Error: ${data.error}` : '') ||
        'Empty response.'
      setChatMessages([...thread, { role: 'assistant', content: reply }])
    } catch (err) {
      setChatMessages([
        ...thread,
        {
          role: 'assistant',
          content: err instanceof Error ? err.message : 'The concierge could not reply — please try again shortly.',
        },
      ])
    } finally {
      setChatLoading(false)
    }
  }

  const clearAgentChat = () => {
    setChatMessages([])
    try {
      localStorage.removeItem(CHAT_STORAGE_KEY)
    } catch {
      /* ignore */
    }
  }

  const showOrder = mode === 'keywords'
  const activeMode = MODES.find((m) => m.value === mode)
  const modeHint = activeMode?.hint ?? ''
  const modeLabel = activeMode?.label ?? ''
  const hasResults = results.length > 0
  const showSaveUi = isSupabaseConfigured() && session != null
  const classicShelfCaption =
    'Hand-picked Gutenberg gems — open anything in a tap.' +
    (showSaveUi ? ' Save favourites while you browse.' : '')
  const showClassicShelfRow = classicShelfBooks.length > 0

  const toggleSavedBook = async (bookId: number, title: string) => {
    if (!session) return
    setSavingId(bookId)
    try {
      if (savedIds.has(bookId)) {
        await unsaveBook(session, bookId)
      } else {
        await saveBook(session, bookId, title)
      }
      await refreshSaved()
    } catch (err) {
      setError(err instanceof Error ? err.message : "We couldn't update your saved list. Try again.")
    } finally {
      setSavingId(null)
    }
  }

  return (
    <div className="app">
      {session && (
        <UserProfileModal
          open={profileOpen}
          onClose={() => setProfileOpen(false)}
          session={session}
          savedList={savedList}
          savingId={savingId}
          onToggleSaved={(bookId, title) => void toggleSavedBook(bookId, title)}
        />
      )}
      <div className="ambient" aria-hidden />

      <a href="#main-content" className="skip-link">
        Skip to search and results
      </a>

      <nav className="topbar">
        <div className="topbar-inner">
          <a className="brand-block" href="/">
            <LogoMark />
            <div className="brand-text">
              <span className="brand-name">Intelli Library</span>
              <span className="brand-tag">
                Free classics · intelligent search inside chapters · smart matched picks · AI brief & chat
              </span>
            </div>
          </a>
          <div className="topbar-end">
            <div className="trust-strip">
              <span className="trust-pill">
                <span className="trust-dot" aria-hidden />
                Ready to search
              </span>
              <div className="kpi-strip" aria-label="Collection size">
                {statsLoadState === 'loading' ? (
                  <span className="kpi-muted">Loading…</span>
                ) : statsLoadState === 'ready' && stats ? (
                  <>
                    <span title="Titles available to search">
                      <strong>{formatNum(stats.documents)}</strong> works
                    </span>
                    <span className="kpi-dot">·</span>
                    <span title="Rough count of distinct words findable by search">
                      <strong>{formatNum(stats.terms)}</strong> words in search
                    </span>
                  </>
                ) : (
                  <span className="kpi-muted" title="Search service unavailable">
                    Search unavailable — try again shortly
                  </span>
                )}
              </div>
            </div>
            <SupabaseAuthChip onOpenProfile={() => setProfileOpen(true)} />
          </div>
        </div>
      </nav>

      <header className="hero">
        <h1 className="hero-title">
          <span className="hero-title-main">Find that passage you&apos;re chasing</span>
          <span className="hero-accent">full-text · related titles · saved books · ai brief & chat</span>
        </h1>
        <p className="hero-lede">
          <span className="hero-lede-row">Search inside books—not summaries alone.</span>
          <span className="hero-lede-row">Related titles beside results.</span>
          <span className="hero-lede-row">Sign in to save books on your shelf.</span>
          <span className="hero-lede-row">
            Brief &amp; chat follow what&apos;s on your screen — open links when you need the exact passage.
          </span>
        </p>
        <div className="hero-badges">
          <span className="badge">Search inside books</span>
          <span className="badge">Related titles</span>
          <span className="badge badge-ai">AI brief & chat</span>
        </div>
      </header>

      <main id="main-content" className="main-shell" tabIndex={-1}>
        <section className="command-panel">
          <form className="search-card" onSubmit={(e) => void runSearch(e)}>
            <div className="controls-row">
              <div className="mode-controls-column">
                <span className="mode-cluster-heading" id="search-mode-heading">
                  Search mode
                </span>
                <div className="mode-cluster" role="group" aria-labelledby="search-mode-heading">
                  {MODES.map((m) => (
                    <button
                      key={m.value}
                      type="button"
                      className={`mode-chip ${mode === m.value ? 'is-active' : ''}`}
                      aria-pressed={mode === m.value}
                      onClick={() => setMode(m.value)}
                    >
                      {m.label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="controls-meta">
                <p className="mode-caption" aria-live="polite">
                  <span className="mode-caption-prefix">Using </span>
                  <strong className="mode-caption-strong">{modeLabel}</strong>
                  <span className="mode-caption-colon">: </span>
                  <span>{modeHint}</span>
                </p>
                {showOrder && (
                  <label className="sort-wrap">
                    <span className="sort-label">Rank by</span>
                    <select
                      className="sort-select"
                      value={order}
                      onChange={(e) => setOrder(e.target.value as RankingOrder)}
                    >
                      {ORDERS.map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
              </div>
            </div>

            <label className="visually-hidden" htmlFor="main-q">
              Search the library
            </label>
            <div className="search-bar">
              <span className="search-icon" aria-hidden>
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="11" cy="11" r="7" />
                  <path d="M21 21l-4.3-4.3" strokeLinecap="round" />
                </svg>
              </span>
              <input
                id="main-q"
                className="search-field"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value)
                  if (queryHint) setQueryHint(null)
                }}
                placeholder="Try themes, places, or phrases — sea voyages, Victorian London, moonlight…"
                autoComplete="off"
                spellCheck={false}
              />
              <button type="submit" className="btn-submit" disabled={loading}>
                <span>{loading ? 'Searching…' : 'Search'}</span>
              </button>
            </div>

            <div className="keyword-panel">
              <div className="keyword-panel-head">
                <span className="keyword-panel-title">Try these themes</span>
                <span className="keyword-panel-rule" aria-hidden />
                <p className="keyword-panel-desc">
                  Quick taps below jump straight into popular literary motifs. Switch modes above to hunt by title or
                  author instead.
                </p>
              </div>
              <div className="keyword-cloud" role="group" aria-label="Suggested searches">
                {STARTER_WORDS.map((q) => (
                  <button
                    key={q}
                    type="button"
                    className="keyword-leaf"
                    onClick={() => void runSearch(undefined, q)}
                    title={`Search for “${q}”`}
                  >
                    <span className="keyword-leaf-word">{displayWord(q)}</span>
                  </button>
                ))}
              </div>
            </div>
          </form>

          <details className="panel-analysis">
            <summary className="panel-analysis-summary">
              <span className="panel-analysis-title">Index insights</span>
              <span className="panel-analysis-sub">Quick facts · last search</span>
            </summary>
            <div className="panel-analysis-grid">
              <div className="panel-analysis-col">
                <h3 className="panel-analysis-h">Library snapshot</h3>
                <dl className="panel-analysis-dl">
                  <div>
                    <dt>Works searchable</dt>
                    <dd>{statsLoadState === 'ready' && stats ? formatNum(stats.documents) : '—'}</dd>
                  </div>
                  <div>
                    <dt>Vocabulary breadth</dt>
                    <dd>{statsLoadState === 'ready' && stats ? formatNum(stats.terms) : '—'}</dd>
                  </div>
                  <div>
                    <dt>Average depth</dt>
                    <dd>{statsLoadState === 'ready' && stats ? formatAvgTokens(stats.avg_doc_length) : '—'}</dd>
                  </div>
                  <div>
                    <dt>Index refreshed</dt>
                    <dd className="panel-analysis-mono">
                      {statsLoadState === 'ready' && stats?.last_full_build
                        ? stats.last_full_build
                        : statsLoadState === 'error'
                          ? 'Unavailable'
                          : '—'}
                    </dd>
                  </div>
                </dl>
              </div>
              <div className="panel-analysis-col">
                <h3 className="panel-analysis-h">Last search</h3>
                {insightsSnap ? (
                  <dl className="panel-analysis-dl">
                    <div>
                      <dt>Query</dt>
                      <dd className="panel-analysis-mono">{insightsSnap.q}</dd>
                    </div>
                    <div>
                      <dt>Mode · rank</dt>
                      <dd>
                        {MODES.find((m) => m.value === insightsSnap.mode)?.label ?? insightsSnap.mode}
                        {' · '}
                        {ORDERS.find((o) => o.value === insightsSnap.order)?.label ?? insightsSnap.order}
                      </dd>
                    </div>
                    <div>
                      <dt>Results shown</dt>
                      <dd>{formatNum(insightsSnap.hits)}</dd>
                    </div>
                    <div>
                      <dt>Response time</dt>
                      <dd>{formatBackendTiming(insightsSnap.ms)}</dd>
                    </div>
                  </dl>
                ) : (
                  <p className="panel-analysis-empty">Search once — numbers from your last query show here.</p>
                )}
              </div>
            </div>
          </details>
        </section>

        {queryHint && (
          <div className="banner banner-hint" role="status">
            {queryHint}
          </div>
        )}

        {error && (
          <div className="banner banner-error" role="alert">
            {error}
          </div>
        )}

        {statsLoadState === 'error' && (
          <div className="banner banner-api" role="alert">
            <p className="banner-api-lead">
              <strong>The library is offline right now.</strong> Refresh in a moment, or let us know if it keeps
              happening — search and helpers will be back as soon as the connection returns.
            </p>
            <details className="banner-api-details">
              <summary className="banner-api-summary">Developer checklist</summary>
              <p className="banner-api-devcopy">
                Start the API from the <code className="banner-code">library</code> folder (
                <code className="banner-code">python manage.py runserver 127.0.0.1:8000</code>) and keep the web app dev
                server running so <code className="banner-code">/api</code> proxies correctly.
              </p>
            </details>
          </div>
        )}

        {showClassicShelfRow && (
          <section className="popular-shelf panel panel-zone panel-zone-classics" aria-labelledby="classic-shelf-heading">
            <header className="popular-shelf-head">
              <div>
                <p className="panel-zone-kicker panel-zone-kicker-classics">Curated shelf</p>
                <h2 id="classic-shelf-heading" className="popular-shelf-title">
                  Classic masterpieces
                </h2>
                <p className="popular-shelf-sub">{classicShelfCaption}</p>
              </div>
            </header>
            <div className="popular-track-scroll">
              <ul className="popular-track">
                {classicShelfBooks.map((b) => (
                  <li key={b.book_id} className="popular-track-item">
                    <PopularCoverCard
                      book={b}
                      showSave={showSaveUi}
                      saved={savedIds.has(b.book_id)}
                      saveBusy={savingId === b.book_id}
                      onToggleSave={() => void toggleSavedBook(b.book_id, b.title)}
                    />
                  </li>
                ))}
              </ul>
            </div>
          </section>
        )}

        <div className="workspace">
          <section className="panel panel-results panel-zone panel-zone-results" aria-labelledby="results-heading">
            <header className="panel-head">
              <div>
                <p className="panel-zone-kicker panel-zone-kicker-results">Your results</p>
                <h2 id="results-heading" className="panel-title">
                  Results
                </h2>
                <p className="panel-sub">
                  {searchMeta
                    ? `${searchMeta.total} title${searchMeta.total === 1 ? '' : 's'} found${searchMeta.ms != null ? ` · ${Math.round(searchMeta.ms)} ms` : ''}`
                    : 'Titles that match your search appear here.'}
                </p>
              </div>
            </header>

            <div className="result-stack">
              {loading ? (
                <div className="skeleton-stack" aria-busy aria-label="Loading results">
                  {[1, 2, 3, 4].map((k) => (
                    <div key={k} className="skeleton-card">
                      <div className="skeleton-line w-30" />
                      <div className="skeleton-line w-80" />
                      <div className="skeleton-line w-60" />
                    </div>
                  ))}
                </div>
              ) : results.length === 0 ? (
                <div className="empty-state">
                  {!searchMeta ? (
                    <>
                      <div className="empty-art" aria-hidden />
                      <p className="empty-title">Ready when you are</p>
                      <p className="empty-copy">
                        {statsLoadState === 'error' ? (
                          <>
                            The library service isn&apos;t responding yet — see the notice above. Once it&apos;s online,
                            every search opens instantly from here.
                          </>
                        ) : (
                          <>
                            Tap a theme chip or type your own words. No rush yet — try a broader phrase if the list stays
                            empty.
                          </>
                        )}
                      </p>
                    </>
                  ) : (
                    <>
                      <p className="empty-title">No matches yet</p>
                      <p className="empty-copy">
                        Try another phrase or switch search mode. This topic might sit outside what&apos;s in the shelves
                        right now — cast the net wider and search again.
                      </p>
                    </>
                  )}
                </div>
              ) : (
                <ul className="hits">
                  {results.map((r, i) => (
                    <li
                      key={`${r.book_id ?? i}-${i}`}
                      className={['hit-row', r.book_id == null ? 'hit-row-no-cover' : ''].filter(Boolean).join(' ')}
                    >
                      <span className="hit-rank" aria-label={`Result rank ${i + 1}`}>
                        {String(i + 1).padStart(2, '0')}
                      </span>
                      {r.book_id != null ? (
                        <BookCoverThumb
                          bookId={r.book_id}
                          coverUrl={r.cover_url}
                          title={r.title}
                          authors={r.authors}
                          preferOpenLibrary
                          frameClassName="hit-cover-frame"
                          imgClassName="hit-cover-img"
                        />
                      ) : null}
                      <div className="hit-body">
                        <a
                          className="hit-title"
                          href={r.gutenberg_url ?? '#'}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {r.title || `Title #${r.book_id}`}
                        </a>
                        {showSaveUi && r.book_id != null ? (
                          <div className="hit-actions">
                            <div className="hit-actions-end">
                              <SaveBookButton
                                saved={savedIds.has(r.book_id)}
                                busy={savingId === r.book_id}
                                onClick={() => void toggleSavedBook(r.book_id!, r.title ?? '')}
                              />
                            </div>
                          </div>
                        ) : null}
                        <div className="hit-meta">
                          <span className="hit-authors">
                            {(r.authors ?? []).join(', ') || 'Author unknown'}
                          </span>
                          {typeof r.score === 'number' && !Number.isNaN(r.score) ? (
                            <span className="hit-score">
                              <span className="hit-score-label">Match</span>
                              <span className="hit-score-value">{r.score.toFixed(3)}</span>
                            </span>
                          ) : null}
                        </div>
                        {r.snippet && (
                          <p
                            className="hit-snippet"
                            dangerouslySetInnerHTML={{ __html: r.snippet }}
                          />
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>

          <aside className="rail" aria-label="Saved books, reading help, and suggestions">
            <div className="panel panel-copilot panel-zone panel-zone-copilot">
              <p className="panel-zone-kicker">Reading companion</p>
              <p className="reading-companion-intro">
                Once you have results, get a short note or ask questions — right next to what you&apos;re reading.
              </p>
              <div className="copilot-header">
                <IconSpark />
                <div>
                  <h2 className="copilot-title">AI reading brief</h2>
                  <p className="copilot-sub">A compact take on what you found — good before you open a book.</p>
                </div>
              </div>

              <div className={`copilot-body ${!hasResults ? 'is-idle' : ''}`}>
                {!hasResults ? (
                  <>
                    <p className="copilot-idle-copy">Search above first — then you can ask for a note or a conversation here.</p>
                  </>
                ) : (
                  <>
                    <button type="button" className="btn-ai-primary" disabled={aiLoading} onClick={() => void runAi()}>
                      {aiLoading ? (
                        <span className="btn-ai-inner">
                          <span className="spinner" aria-hidden />
                          Drafting…
                        </span>
                      ) : (
                        'Generate reading brief'
                      )}
                    </button>
                    <p className="copilot-disclaimer">For wording you’ll quote, still open the book links yourself.</p>
                  </>
                )}
              </div>

              {aiText && (
                <div className="ai-output-card">
                  <span className="ai-output-label">Brief</span>
                  <div className="ai-output-text ibe-markdown">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{aiText}</ReactMarkdown>
                  </div>
                </div>
              )}

              <div className="assistant-chat" aria-label="Research concierge chat">
                <div className="assistant-chat-head">
                  <h3 className="assistant-chat-title">Research concierge</h3>
                </div>
                <button type="button" className="assistant-chat-clear" onClick={clearAgentChat}>
                  Clear conversation
                </button>
                <p className="assistant-chat-hint">
                  Chat in everyday language — compare titles, ask what to read next, or dig into a theme. Switching topics?
                  Clear first so replies don&apos;t get tangled with an older question.
                </p>
                <div className="assistant-chat-thread" role="log" aria-live="polite">
                  {chatMessages.length === 0 ? (
                    <p className="assistant-chat-empty">
                      Try asking about sea voyages, moonlit scenes, or an author you like.
                    </p>
                  ) : (
                    chatMessages.map((m, i) => (
                      <div
                        key={`${i}-${m.role}-${m.content.slice(0, 12)}`}
                        className={`assistant-msg-row assistant-msg-row-${m.role}`}
                      >
                        <div className={`assistant-msg assistant-msg-${m.role}`}>
                          <span className="assistant-msg-label">{m.role === 'user' ? 'You' : 'Assistant'}</span>
                          <div
                            className={
                              m.role === 'assistant' ? 'assistant-msg-body ibe-markdown' : 'assistant-msg-body'
                            }
                          >
                            {m.role === 'assistant' ? (
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                            ) : (
                              m.content
                            )}
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
                <div className="assistant-chat-input-row">
                  <textarea
                    className="assistant-chat-input"
                    rows={2}
                    value={chatInput}
                    placeholder="e.g. Sea adventures like Stevenson"
                    disabled={chatLoading}
                    onChange={(e) => setChatInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault()
                        void sendAgentChat()
                      }
                    }}
                  />
                  <button type="button" className="assistant-chat-send" disabled={chatLoading} onClick={() => void sendAgentChat()}>
                    {chatLoading ? 'Sending…' : 'Send'}
                  </button>
                </div>
              </div>
            </div>

            <div className="panel panel-saved panel-zone panel-zone-saved">
              <p className="panel-zone-kicker">Your library</p>
              <h2 className="panel-title panel-title-sm">Saved titles</h2>
              <p className="panel-sub panel-sub-tight">Saved securely to your account when you sign in.</p>
              {!isSupabaseConfigured() ? (
                <p className="saved-empty">Bookmarks across phones and laptops unlock once sign-in goes live here.</p>
              ) : !session ? (
                <p className="saved-empty">Sign in via Account (top right) to sync bookmarks across devices.</p>
              ) : savedList.length === 0 ? (
                <p className="saved-empty">
                  Tap Save beside any result, similar title, or curated tile — your personal shelf fills in instantly.
                </p>
              ) : (
                <ul className="saved-ul">
                  {savedList.map((row) => (
                    <li key={row.book_id} className="saved-row">
                      <BookCoverThumb
                        bookId={row.book_id}
                        title={row.title}
                        authors={undefined}
                        preferOpenLibrary
                        frameClassName="hit-cover-frame saved-cover-frame"
                        imgClassName="hit-cover-img"
                      />
                      <a
                        className="saved-title"
                        href={`https://www.gutenberg.org/ebooks/${row.book_id}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {row.title?.trim() || `Book ${row.book_id}`}
                      </a>
                      <button
                        type="button"
                        className="saved-remove"
                        title="Remove from saved"
                        disabled={savingId === row.book_id}
                        onClick={() => void toggleSavedBook(row.book_id, row.title ?? '')}
                      >
                        ×
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="panel panel-rec panel-zone panel-zone-rec">
              <p className="panel-zone-kicker">Related reads</p>
              <h2 className="panel-title panel-title-sm">Similar titles</h2>
              <p className="panel-sub panel-sub-tight">Suggestions based on what you searched — open any title to read.</p>
              <ul className="rec-ul">
                {recs.length === 0 ? (
                  <li className="rec-empty">Shows automatically after each successful search.</li>
                ) : (
                  recs.map((it, i) => {
                    const sim = parseSimilarity01(it.reason)
                    return (
                      <li key={`${it.book_id}-${i}`} className="rec-card">
                        <div className="rec-card-layout">
                          {it.book_id != null ? (
                            <BookCoverThumb
                              bookId={it.book_id}
                              coverUrl={it.cover_url}
                              title={it.title}
                              authors={it.authors}
                              preferOpenLibrary
                              frameClassName="rec-cover-frame"
                              imgClassName="rec-cover-img"
                            />
                          ) : (
                            <div className="rec-cover-placeholder" aria-hidden />
                          )}
                          <div className="rec-card-stack">
                            <div className="rec-card-top">
                              <div className="rec-card-title-cluster">
                                <span className="rec-num">{i + 1}</span>
                                <a href={it.gutenberg_url ?? '#'} target="_blank" rel="noreferrer" className="rec-title">
                                  {it.title || `#${it.book_id}`}
                                </a>
                              </div>
                              {showSaveUi && it.book_id != null && (
                                <SaveBookButton
                                  compact
                                  saved={savedIds.has(it.book_id)}
                                  busy={savingId === it.book_id}
                                  onClick={() => void toggleSavedBook(it.book_id!, it.title ?? '')}
                                />
                              )}
                            </div>
                            {sim != null && (
                              <div className="sim-bar-wrap">
                                <div className="sim-bar" style={{ width: `${sim * 100}%` }} />
                                <span className="sim-label">Relevance {(sim * 100).toFixed(0)}%</span>
                              </div>
                            )}
                          </div>
                        </div>
                      </li>
                    )
                  })
                )}
              </ul>
            </div>
          </aside>
        </div>
      </main>

      <footer className="site-footer">
        <p className="site-footer-inner">
          <span>© {new Date().getFullYear()} Intelli Library</span>
          <span className="site-footer-dot" aria-hidden>
            ·
          </span>
          <span>
            Texts from{' '}
            <a href="https://www.gutenberg.org/" target="_blank" rel="noreferrer">
              Project Gutenberg
            </a>
          </span>
          <span className="site-footer-dot" aria-hidden>
            ·
          </span>
          <span className="site-footer-note">
            Reading brief &amp; chat are helpers — follow the book links for the full text.
          </span>
        </p>
      </footer>
    </div>
  )
}
