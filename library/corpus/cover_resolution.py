"""
Resolve book cover URLs: stored Open Library (or other HTTPS) URL first, then PG default.

`corpus/data/curated_cover_urls.json` is filled by `manage.py sync_curated_cover_urls`
so homepage classics work before every title exists in `books`.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from corpus.models import Book

_DATA_PATH = Path(__file__).resolve().parent / "data" / "curated_cover_urls.json"


@lru_cache(maxsize=1)
def _curated_json_raw() -> dict[str, str]:
    if not _DATA_PATH.is_file():
        return {}
    try:
        raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in raw.items():
        if isinstance(k, str) and isinstance(v, str) and v.strip().startswith(("http://", "https://")):
            out[k.strip()] = v.strip()
    return out


def curated_cover_url_fallback(book_id: int) -> str | None:
    return _curated_json_raw().get(str(book_id))


def invalidate_curated_cover_cache() -> None:
    _curated_json_raw.cache_clear()


def resolve_cover_url(book_id: int, book: Book | None = None) -> str:
    if book is not None:
        stored = (book.cover_image_url or "").strip()
        if stored.startswith("http://") or stored.startswith("https://"):
            return stored
    fb = curated_cover_url_fallback(book_id)
    if fb:
        return fb
    return (
        f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.cover.medium.jpg"
    )
