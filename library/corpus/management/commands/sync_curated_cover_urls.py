"""
Fetch Open Library cover URLs for CURATED_CLASSICS and persist them.

Writes:
  - corpus/data/curated_cover_urls.json (always; homepage classics + fallback)
  - books.cover_image_url when a Book row exists for that PG id

Open Library ToU: polite traffic only; default throttle between requests.

Example:
  python manage.py sync_curated_cover_urls
  python manage.py sync_curated_cover_urls --force
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import requests
from django.core.management.base import BaseCommand

from corpus.cover_resolution import invalidate_curated_cover_cache
from corpus.curated_classics import CURATED_CLASSICS
from corpus.models import Book

UA = "Mozilla/5.0 (compatible; IntelliBookEngine/1.2; +https://openlibrary.org/dev/docs/api)"
JSON_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "curated_cover_urls.json"


def _open_library_cover_url(title: str, author_first: str | None, session: requests.Session) -> str | None:
    t = (title or "").strip()
    if not t:
        return None
    params: dict[str, str] = {
        "limit": "5",
        "fields": "cover_i,title,author_name",
        "title": t,
    }
    if author_first and author_first.strip():
        params["author"] = author_first.strip()
    try:
        r = session.get("https://openlibrary.org/search.json", params=params, timeout=45)
        if not r.ok:
            return None
        data = r.json()
    except (requests.RequestException, ValueError, json.JSONDecodeError):
        return None

    docs = data.get("docs") if isinstance(data, dict) else None
    if not isinstance(docs, list):
        return None
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        cid = doc.get("cover_i")
        if isinstance(cid, int) and cid > 0:
            return f"https://covers.openlibrary.org/b/id/{cid}-M.jpg"
        if isinstance(cid, float) and cid > 0:
            return f"https://covers.openlibrary.org/b/id/{int(cid)}-M.jpg"
    return None


class Command(BaseCommand):
    help = "Sync Open Library cover URLs for curated classics → JSON + Book.cover_image_url."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing stored URLs (JSON + DB).",
        )
        parser.add_argument(
            "--sleep",
            type=float,
            default=0.35,
            help="Seconds between Open Library requests (default 0.35).",
        )

    def handle(self, *args, **opts):
        force: bool = opts["force"]
        pause: float = max(0.0, float(opts["sleep"]))

        mapping: dict[str, str] = {}
        if JSON_PATH.is_file():
            try:
                prev = json.loads(JSON_PATH.read_text(encoding="utf-8"))
                if isinstance(prev, dict):
                    for k, v in prev.items():
                        if isinstance(k, str) and isinstance(v, str) and v.startswith("http"):
                            mapping[k] = v.strip()
            except (OSError, json.JSONDecodeError):
                pass

        session = requests.Session()
        session.headers.update({"User-Agent": UA})

        updated = 0
        skipped = 0
        failed = 0

        for book_id, title, authors in CURATED_CLASSICS:
            sid = str(book_id)
            if not force and sid in mapping:
                skipped += 1
                continue

            author_first = authors[0] if authors else None
            url = _open_library_cover_url(title, author_first, session)
            if pause:
                time.sleep(pause)

            if not url:
                self.stdout.write(self.style.WARNING(f"PG#{book_id}: no OL cover — skipped"))
                failed += 1
                continue

            mapping[sid] = url
            updated += 1

            row = Book.objects.filter(text_id=book_id).first()
            if row is not None and (
                force or not ((row.cover_image_url or "").strip().startswith("http"))
            ):
                Book.objects.filter(text_id=book_id).update(cover_image_url=url)

            self.stdout.write(self.style.SUCCESS(f"PG#{book_id}: resolved"))

        JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        JSON_PATH.write_text(json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        invalidate_curated_cover_cache()

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. json_keys={len(mapping)}, newly_resolved={updated}, skipped_already={skipped}, unresolved={failed}"
            )
        )
        self.stdout.write(f"Wrote {JSON_PATH}")
