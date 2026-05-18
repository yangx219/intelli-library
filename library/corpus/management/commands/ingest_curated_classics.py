"""
Download plaintext for homepage curated classics into your corpus folder and append CSV rows.

Project Gutenberg serves several URL shapes per ebook; we try a small list until one returns body text.

After this command completes, rebuild the inverted index (full rebuild — same as `index_build_fast` expects):

  python manage.py index_build_fast --dir ../books_html_kept --meta ../data/selected_meta.csv
  python manage.py index_compute_tfidf
  python manage.py build_doc_graph
  python manage.py compute_centrality

Adjust --dir / --meta paths if your repo layout differs (run from `library/`).
"""

from __future__ import annotations

import csv
from pathlib import Path

import requests
from django.core.management.base import BaseCommand

from corpus.curated_classics import CURATED_CLASSICS

META_FIELDS = ["Text#", "Title", "Authors", "Language", "Issued", "URL", "Words"]

UA = "Mozilla/5.0 (compatible; IntelliBookEngine/1.1; +https://www.gutenberg.org/policy/robot_access)"


def _candidate_urls(book_id: int) -> list[str]:
    return [
        f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt",
        f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt.utf-8",
        f"https://www.gutenberg.org/files/{book_id}/{book_id}-0.txt",
        f"https://www.gutenberg.org/files/{book_id}/{book_id}.txt",
    ]


def _download_body(book_id: int, timeout: int = 90) -> bytes | None:
    headers = {"User-Agent": UA}
    for url in _candidate_urls(book_id):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            if r.status_code == 200 and len(r.content) > 800:
                return r.content
        except requests.RequestException:
            continue
    return None


def _authors_cell(authors: list[str]) -> str:
    return "; ".join(a.strip() for a in authors if a.strip())


class Command(BaseCommand):
    help = (
        "Download curated classics as UTF-8 .txt into --dir and append rows to --meta "
        "(then run index_build_fast + graph / centrality)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dir",
            default="../books_html_kept",
            help="Corpus directory (expects `{id}.txt` filenames, same as index_build_fast).",
        )
        parser.add_argument(
            "--meta",
            default="../data/selected_meta.csv",
            help="selected_meta.csv path (Text#, Title, Authors, ...).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print actions without writing files or mutating CSV.",
        )

    def handle(self, *args, **opts):
        book_dir = Path(opts["dir"]).resolve()
        meta_csv = Path(opts["meta"]).resolve()
        dry = bool(opts["dry_run"])

        book_dir.mkdir(parents=True, exist_ok=True)

        existing_meta_ids: set[int] = set()
        if meta_csv.is_file():
            with meta_csv.open(encoding="utf-8", errors="ignore", newline="") as f:
                for row in csv.DictReader(f):
                    tid = (row.get("Text#") or "").strip()
                    if tid.isdigit():
                        existing_meta_ids.add(int(tid))

        appended_rows = 0
        downloaded = 0
        already_disk = 0

        for book_id, title, authors in CURATED_CLASSICS:
            dest = book_dir / f"{book_id}.txt"
            have_file = dest.is_file() and dest.stat().st_size > 800

            if have_file:
                already_disk += 1
            elif dry:
                self.stdout.write(f"[dry-run] would download PG#{book_id} → {dest}")
            else:
                blob = _download_body(book_id)
                if not blob:
                    self.stdout.write(self.style.WARNING(f"PG#{book_id}: download failed — skipped"))
                    continue
                text = blob.decode("utf-8", errors="replace")
                dest.write_text(text, encoding="utf-8")
                downloaded += 1
                have_file = True

            if book_id in existing_meta_ids:
                continue

            wc = 1
            if have_file and not dry:
                wc = len(dest.read_text(encoding="utf-8", errors="ignore").split())

            row = {
                "Text#": str(book_id),
                "Title": title,
                "Authors": _authors_cell(authors),
                "Language": "en",
                "Issued": "",
                "URL": f"https://www.gutenberg.org/ebooks/{book_id}",
                "Words": str(max(wc, 1)),
            }

            if dry:
                self.stdout.write(f"[dry-run] would append CSV Text#={book_id}")
                appended_rows += 1
                existing_meta_ids.add(book_id)
                continue

            append_header = not meta_csv.exists() or meta_csv.stat().st_size == 0
            with meta_csv.open("a", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=META_FIELDS)
                if append_header:
                    w.writeheader()
                w.writerow(row)
            appended_rows += 1
            existing_meta_ids.add(book_id)
            self.stdout.write(self.style.SUCCESS(f"CSV +{book_id} — {title[:56]}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. new_downloads={downloaded}, already_on_disk={already_disk}, csv_rows_appended={appended_rows}"
            )
        )
        self.stdout.write(
            "If the SQLite index is empty / brand-new corpus: python manage.py index_build_fast "
            f"--dir {book_dir} --meta {meta_csv}"
        )
        self.stdout.write(
            "If you ALREADY have a large index (slow full rebuild): python manage.py index_append_curated_classics "
            f"--dir {book_dir}"
        )
        self.stdout.write(
            "Always next: python manage.py index_compute_tfidf"
        )
        self.stdout.write(
            "Optional (slow): python manage.py build_doc_graph && python manage.py compute_centrality"
        )
