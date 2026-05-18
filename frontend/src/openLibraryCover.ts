/**
 * Open Library search → cover image URL (browser fetch). Many Project Gutenberg IDs have no
 * cached cover on gutenberg.org; OL often has a reasonable match by title + author.
 */

export function isOpenLibraryCoverUrl(url: string | null | undefined): boolean {
  const u = (url ?? '').trim().toLowerCase()
  return u.startsWith('http') && u.includes('covers.openlibrary.org')
}

const cache = new Map<string, string | null>()

function cacheKey(title: string, authorFirst?: string | null): string {
  return `v2|${title.trim().toLowerCase()}|${(authorFirst ?? '').trim().toLowerCase()}`
}

/** PG catalogue lines look like `Twain, Mark, 1835-1910`; OL matches better as `Mark Twain`. */
function normalizeAuthorForOpenLibrary(raw?: string | null): string | undefined {
  const s = raw?.trim()
  if (!s) return undefined
  let x = s.replace(/,\s*\d{4}(?:–|-|—)?(?:\d{4})?\s*$/u, '').trim()
  x = x.replace(/\[[^\]]*]/g, '').trim()
  const commaIdx = x.indexOf(',')
  if (commaIdx <= 0) return x.split(/\s+/).slice(0, 5).join(' ')
  const last = x.slice(0, commaIdx).trim()
  let first = x.slice(commaIdx + 1).trim()
  first = first.split(',')[0]?.trim() ?? ''
  if (last && first) return `${first} ${last}`
  return last || first || undefined
}

/** Long PG mega-titles rarely hit OL; strip boilerplate and shorten. */
function titleCandidates(raw: string): string[] {
  const t = raw.trim()
  const acc: string[] = []
  const add = (s: string) => {
    const x = s.trim().replace(/\s+/g, ' ')
    if (x.length >= 2 && !acc.includes(x)) acc.push(x)
  }
  add(t)
  const deblob = t.replace(/\bproject\s+gutenberg\b/gi, ' ').replace(/\s+/g, ' ').trim()
  add(deblob)
  add(deblob.slice(0, 120))
  add(deblob.slice(0, 72))
  add(deblob.replace(/^the\s+/i, '').slice(0, 72))
  return acc.slice(0, 6)
}

function pickCoverFromDocs(docs: unknown[]): string | null {
  for (const d of docs) {
    if (!d || typeof d !== 'object') continue
    const cid = (d as { cover_i?: unknown }).cover_i
    if (typeof cid === 'number' && cid > 0) {
      return `https://covers.openlibrary.org/b/id/${Math.floor(cid)}-M.jpg`
    }
  }
  return null
}

async function fetchOlOnce(titleQ: string, author?: string): Promise<string | null> {
  const params = new URLSearchParams({
    limit: '8',
    fields: 'cover_i,title,author_name',
  })
  params.append('title', titleQ)
  if (author?.trim()) params.append('author', author.trim())

  const res = await fetch(`https://openlibrary.org/search.json?${params}`)
  if (!res.ok) return null
  const data = (await res.json()) as { docs?: unknown[] }
  const docs = Array.isArray(data.docs) ? data.docs : []
  return pickCoverFromDocs(docs)
}

/** Last resort: PG mega-volumes often miss title hits but OL has covers under that author. */
async function fetchOlAuthorOnly(author: string): Promise<string | null> {
  const a = author.trim()
  if (!a) return null
  const params = new URLSearchParams({
    limit: '15',
    fields: 'cover_i,title,author_name',
    author: a,
  })
  const res = await fetch(`https://openlibrary.org/search.json?${params}`)
  if (!res.ok) return null
  const data = (await res.json()) as { docs?: unknown[] }
  const docs = Array.isArray(data.docs) ? data.docs : []
  return pickCoverFromDocs(docs)
}

export async function fetchOpenLibraryCoverUrl(
  title: string,
  authorFirst?: string | null,
): Promise<string | null> {
  const t = title.trim()
  if (!t) return null
  const key = cacheKey(t, authorFirst)
  if (cache.has(key)) return cache.get(key) ?? null

  const authorNorm = normalizeAuthorForOpenLibrary(authorFirst)

  try {
    for (const tq of titleCandidates(t)) {
      let url = await fetchOlOnce(tq, authorNorm)
      if (!url) url = await fetchOlOnce(tq, undefined)
      if (url) {
        cache.set(key, url)
        return url
      }
    }
    if (authorNorm) {
      const byAuthor = await fetchOlAuthorOnly(authorNorm)
      if (byAuthor) {
        cache.set(key, byAuthor)
        return byAuthor
      }
    }
    cache.set(key, null)
    return null
  } catch {
    cache.set(key, null)
    return null
  }
}
