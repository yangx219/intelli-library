import type { PopularBook } from './api'

/**
 * Mirrors `_CURATED_CLASSICS` in library/corpus/views.py — keep lists in sync when editing either side.
 */
const STATIC_CURATED_RAW: [number, string, string[]][] = [
  [1342, 'Pride and Prejudice', ['Jane Austen']],
  [1260, 'Jane Eyre', ['Charlotte Brontë']],
  [98, 'A Tale of Two Cities', ['Charles Dickens']],
  [1400, 'Great Expectations', ['Charles Dickens']],
  [766, 'David Copperfield', ['Charles Dickens']],
  [2701, 'Moby Dick', ['Herman Melville']],
  [1661, 'The Adventures of Sherlock Holmes', ['Arthur Conan Doyle']],
  [84, 'Frankenstein', ['Mary Wollstonecraft Shelley']],
  [345, 'Dracula', ['Bram Stoker']],
  [768, 'Wuthering Heights', ['Emily Brontë']],
  [158, 'Emma', ['Jane Austen']],
  [161, 'Sense and Sensibility', ['Jane Austen']],
  [174, 'The Picture of Dorian Gray', ['Oscar Wilde']],
  [120, 'Treasure Island', ['Robert Louis Stevenson']],
  [11, "Alice's Adventures in Wonderland", ['Lewis Carroll']],
  [74, 'The Adventures of Tom Sawyer', ['Mark Twain']],
  [33, 'The Scarlet Letter', ['Nathaniel Hawthorne']],
  [2600, 'War and Peace', ['Leo Tolstoy']],
  [1399, 'Anna Karenina', ['Leo Tolstoy']],
  [996, 'Don Quixote', ['Miguel de Cervantes']],
  [1184, 'The Count of Monte Cristo', ['Alexandre Dumas']],
  [1513, 'Romeo and Juliet', ['William Shakespeare']],
  [2591, "Grimms' Fairy Tales", ['Jacob Grimm', 'Wilhelm Grimm']],
  [730, 'Oliver Twist', ['Charles Dickens']],
]

const EBOOK_BASE = 'https://www.gutenberg.org/ebooks/'

function gutenbergCoverUrl(bookId: number): string {
  return `https://www.gutenberg.org/cache/epub/${bookId}/pg${bookId}.cover.medium.jpg`
}

/** Used when `/api/catalog/classics` is unreachable (e.g. Django not running). */
export function staticCuratedClassics(limit = 12): PopularBook[] {
  const cap = Math.max(1, Math.min(limit, 24))
  const seen = new Set<number>()
  const out: PopularBook[] = []
  for (const [bookId, title, authors] of STATIC_CURATED_RAW) {
    if (seen.has(bookId)) continue
    seen.add(bookId)
    out.push({
      book_id: bookId,
      title,
      authors,
      gutenberg_url: `${EBOOK_BASE}${bookId}`,
      cover_url: gutenbergCoverUrl(bookId),
    })
    if (out.length >= cap) break
  }
  return out
}
