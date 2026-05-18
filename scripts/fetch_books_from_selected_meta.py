#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Download Project Gutenberg full-text (HTML → plain) for each Text# listed in selected_meta.csv.

Writes: <repo>/books_html_kept/{id}.txt (same layout expected by index_build_fast).

Run from repo root:
  python scripts/fetch_books_from_selected_meta.py --limit 50
  python scripts/fetch_books_from_selected_meta.py

Requires: requests, beautifulsoup4 (see library/requirements.txt).
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
META_DEFAULT = ROOT / "data" / "selected_meta.csv"
OUT_DEFAULT = ROOT / "books_html_kept"

TIMEOUT = 45
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; IntelliBookEngine/1.0; +https://www.gutenberg.org/policy/robot_access)"
    )
}

START_RE = re.compile(r"\*{3}\s*START OF .*?PROJECT GUTENBERG EBOOK.*?\*{3}", re.I)


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    body = soup.body or soup
    text = body.get_text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines()]
    norm: list[str] = []
    blank = False
    for ln in lines:
        if ln:
            norm.append(ln)
            blank = False
        else:
            if not blank:
                norm.append("")
            blank = True
    return "\n".join(norm).strip()


def build_html_urls(book_id: str) -> list[str]:
    return [
        f"https://www.gutenberg.org/files/{book_id}/{book_id}-h/{book_id}-h.htm",
        f"https://www.gutenberg.org/files/{book_id}/{book_id}-h.htm",
        f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.html",
    ]


def fetch_one(book_id: str) -> tuple[str | None, str | None]:
    for url in build_html_urls(book_id):
        try:
            r = requests.get(url, timeout=TIMEOUT, headers=HEADERS)
            if r.status_code != 200 or len(r.content) < 1500:
                continue
            text_all = html_to_text(r.text)
            if not START_RE.search(text_all):
                continue
            return text_all, url
        except requests.RequestException:
            continue
    return None, None


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch PG texts for rows in selected_meta.csv")
    ap.add_argument("--meta", type=Path, default=META_DEFAULT, help="CSV path (default: ./data/selected_meta.csv)")
    ap.add_argument("--out-dir", type=Path, default=OUT_DEFAULT, help="Output directory for {id}.txt")
    ap.add_argument("--limit", type=int, default=0, help="Max number of books to fetch (0 = all rows)")
    ap.add_argument("--sleep", type=float, default=0.35, help="Seconds between HTTP requests")
    ap.add_argument("--overwrite", action="store_true", help="Re-download even if .txt exists")
    args = ap.parse_args()

    if not args.meta.exists():
        print(f"CSV not found: {args.meta}", file=sys.stderr)
        return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)

    with args.meta.open(newline="", encoding="utf-8", errors="ignore") as f:
        rows = list(csv.DictReader(f))

    ids: list[str] = []
    for row in rows:
        tid = (row.get("Text#") or "").strip()
        if tid.isdigit():
            ids.append(tid)

    if args.limit > 0:
        ids = ids[: args.limit]

    ok = skip = fail = 0
    for i, tid in enumerate(ids, 1):
        out_path = args.out_dir / f"{tid}.txt"
        if out_path.exists() and not args.overwrite:
            skip += 1
            continue

        text, url = fetch_one(tid)
        if not text:
            fail += 1
            print(f"[{i}/{len(ids)}] FAIL {tid}")
        else:
            out_path.write_text(text, encoding="utf-8")
            ok += 1
            print(f"[{i}/{len(ids)}] OK {tid} <- {url}")

        if args.sleep > 0:
            time.sleep(args.sleep)

    print(f"\nDone: downloaded={ok}, skipped_existing={skip}, failed={fail}, out={args.out_dir}")
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
