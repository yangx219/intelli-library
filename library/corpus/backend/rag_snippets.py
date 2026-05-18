"""Extract short plain-text excerpts from local HTML corpus files for RAG-style prompting."""

from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup
from django.conf import settings

from corpus.models import Book


def keywords_from_user_text(text: str, max_words: int = 12) -> list[str]:
    if not text:
        return []
    words = [w for w in re.split(r"\W+", text.lower()) if len(w) >= 3]
    seen: set[str] = set()
    out: list[str] = []
    for w in words:
        if w in seen:
            continue
        seen.add(w)
        out.append(w)
        if len(out) >= max_words:
            break
    return out


def _allowed_roots() -> list[Path]:
    raw = getattr(settings, "CORPUS_ALLOWED_ROOT", "") or ""
    if not str(raw).strip():
        return []
    return [Path(p.strip()).expanduser().resolve() for p in str(raw).split(",") if p.strip()]


def _path_allowed(path: Path) -> bool:
    roots = _allowed_roots()
    if not roots:
        return True
    try:
        resolved = path.expanduser().resolve()
    except OSError:
        return False
    for root in roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def snippet_from_book(book: Book, keywords: list[str], max_len: int = 720) -> str | None:
    """
    Read `Book.local_path` HTML (if present), strip tags, return a window around the first keyword hit.
    """
    raw_path = (book.local_path or "").strip()
    if not raw_path:
        return None
    path = Path(raw_path)
    if not path.is_file():
        return None
    if not _path_allowed(path):
        return None
    try:
        html = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None

    lower = text.lower()
    pos = -1
    for kw in keywords:
        if len(kw) < 2:
            continue
        idx = lower.find(kw.lower())
        if idx >= 0:
            pos = idx
            break
    if pos < 0:
        pos = 0

    half = max_len // 2
    start = max(0, pos - half)
    chunk = text[start : start + max_len].strip()
    prefix = "…" if start > 0 else ""
    suffix = "…" if start + max_len < len(text) else ""
    return f"{prefix}{chunk}{suffix}"


def rag_block_for_book_ids(query: str, book_ids: list[int], max_books: int = 8) -> str | None:
    """Excerpts for explicit catalogue IDs (e.g. current search results)."""
    ids = []
    for x in book_ids[:max_books]:
        try:
            ids.append(int(x))
        except (TypeError, ValueError):
            continue
    if not ids:
        return None
    kws = keywords_from_user_text(query)
    books = Book.objects.filter(text_id__in=ids)
    book_map = {b.text_id: b for b in books}
    parts: list[str] = []
    for bid in ids:
        b = book_map.get(bid)
        if not b:
            continue
        title = (b.title or "").strip() or f"Book {bid}"
        snip = snippet_from_book(b, kws)
        excerpt = snip or "(No local HTML excerpt.)"
        parts.append(f"[pg:{bid}] {title}\n{excerpt}")
    if not parts:
        return None
    return (
        "Local corpus excerpts for the titles below:\n\n" + "\n\n---\n\n".join(parts)
    )
