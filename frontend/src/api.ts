export type SearchMode = 'keywords' | 'title' | 'author' | 'regex'
export type RankingOrder = 'default' | 'pagerank' | 'closeness' | 'betweenness'

const LIBRARY_OFFLINE_MESSAGE =
  'We can’t reach the library from here. Check your connection, refresh the page, or try again in a moment.'

/** Project Gutenberg medium cover URL for a numeric ebook id. */
export function gutenbergCoverMediumUrl(bookId: number): string {
  return `https://www.gutenberg.org/cache/epub/${bookId}/pg${bookId}.cover.medium.jpg`
}

/** Ordered PG cache URLs — many ebooks only have one size or none; try each until one loads. */
export function gutenbergCoverCandidateUrls(bookId: number, preferred?: string | null): string[] {
  const base = `https://www.gutenberg.org/cache/epub/${bookId}/pg${bookId}`
  const ordered = [
    preferred?.trim() || null,
    `${base}.cover.medium.jpg`,
    `${base}.cover.small.jpg`,
  ].filter((x): x is string => Boolean(x))
  return [...new Set(ordered)]
}

export interface SearchHit {
  book_id?: number
  title?: string
  authors?: string[]
  snippet?: string
  score?: number
  gutenberg_url?: string
  cover_url?: string
}

export interface SearchResponse {
  total: number
  elapsed_ms: number
  results: SearchHit[]
}

export interface IndexStats {
  documents: number
  avg_doc_length: number | null
  terms: number
  last_full_build: string | null
}

export interface RecommendItem {
  book_id?: number
  title?: string
  authors?: string[]
  reason?: string
  gutenberg_url?: string
  cover_url?: string
}

export interface PopularBook {
  book_id: number
  title: string
  authors: string[]
  gutenberg_url: string
  cover_url: string
  pagerank?: number | null
  /** From `/api/catalog/classics`: false when this PG id is not in your built SQLite index. */
  in_local_index?: boolean
}

/**
 * Production: set `VITE_API_BASE` to your Django public URL (e.g. https://api.example.com), no trailing slash.
 * Leave unset when the browser talks to the same host as the API (reverse proxy serves `/api` on the site origin).
 */
function apiOrigin(): string {
  const raw = import.meta.env.VITE_API_BASE?.trim()
  if (raw) return raw.replace(/\/+$/, '')
  return window.location.origin
}

function apiUrl(path: string): string {
  const base = apiOrigin()
  const p = path.startsWith('/') ? path : `/${path}`
  return `${base}${p}`
}

function buildUrl(path: string, params: Record<string, string | number | undefined>) {
  const u = new URL(apiUrl(path))
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === '') return
    u.searchParams.set(k, String(v))
  })
  return u.toString()
}

async function parseJsonResponse(res: Response): Promise<unknown> {
  const text = await res.text()
  const trimmed = text.trim()
  if (!trimmed) return {}
  try {
    return JSON.parse(trimmed) as unknown
  } catch {
    const snippet = trimmed.slice(0, 180).replace(/\s+/g, ' ')
    throw new Error(
      `The library service returned something unexpected (HTTP ${res.status}). Snippet: ${snippet}`,
    )
  }
}

export async function fetchSearch(
  q: string,
  mode: SearchMode,
  order: RankingOrder,
): Promise<SearchResponse> {
  const url = buildUrl('/api/search', { q, mode, order })
  let res: Response
  try {
    res = await fetch(url, { headers: { Accept: 'application/json' } })
  } catch (e) {
    if (e instanceof TypeError) {
      throw new Error(LIBRARY_OFFLINE_MESSAGE)
    }
    throw e
  }
  const body = await parseJsonResponse(res)
  if (!res.ok) {
    throw new Error(typeof body === 'object' && body && 'detail' in body ? String((body as { detail: unknown }).detail) : JSON.stringify(body))
  }
  return body as SearchResponse
}

export async function fetchRecommendations(q: string, limit = 6) {
  const url = buildUrl('/api/recommendations/query', { q, limit })
  const res = await fetch(url, { headers: { Accept: 'application/json' } })
  const body = await parseJsonResponse(res)
  if (!res.ok) throw new Error(typeof body === 'object' ? JSON.stringify(body) : String(body))
  return body as { items: RecommendItem[] }
}

export async function fetchIndexStats(): Promise<IndexStats> {
  const res = await fetch(apiUrl('/api/index/stats'), { headers: { Accept: 'application/json' } })
  const body = await parseJsonResponse(res)
  if (!res.ok) throw new Error(JSON.stringify(body))
  return body as IndexStats
}

export async function fetchPopularBooks(limit = 12): Promise<{ items: PopularBook[]; fallback: boolean }> {
  const url = buildUrl('/api/catalog/popular', { limit })
  let res: Response
  try {
    res = await fetch(url, { headers: { Accept: 'application/json' } })
  } catch (e) {
    if (e instanceof TypeError) {
      throw new Error(LIBRARY_OFFLINE_MESSAGE)
    }
    throw e
  }
  const body = await parseJsonResponse(res)
  if (!res.ok) throw new Error(typeof body === 'object' ? JSON.stringify(body) : String(body))
  const parsed = body as { items?: PopularBook[]; fallback?: boolean }
  return {
    items: Array.isArray(parsed.items) ? parsed.items : [],
    fallback: Boolean(parsed.fallback),
  }
}

/** Curated classics shelf — same shape as popular tiles but not tied to PageRank. */
export async function fetchClassicBooks(limit = 12): Promise<{ items: PopularBook[] }> {
  const url = buildUrl('/api/catalog/classics', { limit })
  let res: Response
  try {
    res = await fetch(url, { headers: { Accept: 'application/json' } })
  } catch (e) {
    if (e instanceof TypeError) {
      throw new Error(LIBRARY_OFFLINE_MESSAGE)
    }
    throw e
  }
  const body = await parseJsonResponse(res)
  if (!res.ok) throw new Error(typeof body === 'object' ? JSON.stringify(body) : String(body))
  const parsed = body as { items?: PopularBook[] }
  return {
    items: Array.isArray(parsed.items) ? parsed.items : [],
  }
}

export async function fetchAiExplain(query: string, bookTitles: string[], bookIds?: number[]) {
  let res: Response
  try {
    res = await fetch(apiUrl('/api/ai/explain'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({
        query,
        book_titles: bookTitles,
        book_ids: bookIds?.length ? bookIds : undefined,
      }),
    })
  } catch (e) {
    if (e instanceof TypeError) {
      throw new Error(LIBRARY_OFFLINE_MESSAGE)
    }
    throw e
  }
  const body = await parseJsonResponse(res)
  if (!res.ok) throw new Error(JSON.stringify(body))
  return body as {
    explanation?: string | null
    detail?: string
    error?: string
    rag_used?: boolean
  }
}

export type ChatMessage = { role: 'user' | 'assistant' | 'system'; content: string }

export async function fetchAiChat(
  messages: ChatMessage[],
  options?: {
    enableTools?: boolean
    injectRag?: boolean
    /** Main search column state — concierge sees current hits when the user refers to search results */
    searchContext?: {
      query: string
      hits: Array<{ book_id?: number | null; title?: string | null; authors?: string | string[] | null }>
    }
  },
): Promise<{
  reply?: string | null
  detail?: string
  error?: string
  tool_trace?: { tool: string; round: number; argument_chars: number; output_chars: number }[]
  rag_injected?: boolean
  tools_enabled?: boolean
}> {
  let res: Response
  try {
    res = await fetch(apiUrl('/api/ai/chat'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({
        messages,
        enable_tools: options?.enableTools ?? true,
        inject_rag: options?.injectRag ?? true,
        search_context: options?.searchContext,
      }),
    })
  } catch (e) {
    if (e instanceof TypeError) {
      throw new Error(LIBRARY_OFFLINE_MESSAGE)
    }
    throw e
  }
  const body = await parseJsonResponse(res)
  if (!res.ok) throw new Error(JSON.stringify(body))
  return body as {
    reply?: string | null
    detail?: string
    error?: string
    tool_trace?: { tool: string; round: number; argument_chars: number; output_chars: number }[]
    rag_injected?: boolean
    tools_enabled?: boolean
  }
}
