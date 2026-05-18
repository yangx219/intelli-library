#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Télécharger les livres Project Gutenberg (version HTML), vérifier la présence
des informations préliminaires avant « START », ne compter que les mots après
START (≥10 000) et enregistrer le texte brut complet sans suppression.

Run from repo root:
  python scripts/download_and_filter_gutenberg_html.py
"""

import csv
import random
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"

COUNT_TARGET = 1664
MIN_WORDS = 10_000

CATALOG_PATH = DATA_DIR / "pg_catalog.csv"
CATALOG_URL = "https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv"

DEST_FULL = REPO_ROOT / "books_html_kept"
META_CSV = DATA_DIR / "selected_meta.csv"

TIMEOUT = 30
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
}

START_RE = re.compile(r"\*{3}\s*START OF .*?PROJECT GUTENBERG EBOOK.*?\*{3}", re.I)
END_RE = re.compile(r"\*{3}\s*END OF .*?PROJECT GUTENBERG EBOOK.*?\*{3}", re.I)
LICENSE_RE = re.compile(r"START:\s*FULL\s*LICENSE", re.I)
WORD_RE = re.compile(r"[A-Za-z0-9']+")

PREFACE_HINTS = [
    "This ebook is for the use of anyone anywhere",
    "Title:",
    "Author:",
    "Release date:",
    "Language:",
    "Credits:",
]


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def download_catalog_if_needed() -> Path:
    ensure_dir(DATA_DIR)
    if CATALOG_PATH.exists():
        return CATALOG_PATH
    print("Downloading pg_catalog.csv ...")
    r = requests.get(CATALOG_URL, timeout=TIMEOUT, headers=HEADERS)
    r.raise_for_status()
    CATALOG_PATH.write_bytes(r.content)
    print(f"Saved catalog -> {CATALOG_PATH}")
    return CATALOG_PATH


def iter_english_rows(catalog_path: Path):
    with open(catalog_path, newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        rows = [row for row in reader if row.get("Language", "").startswith("en")]
    random.shuffle(rows)
    return rows


def build_html_urls(book_id: str):
    return [
        f"https://www.gutenberg.org/files/{book_id}/{book_id}-h/{book_id}-h.htm",
        f"https://www.gutenberg.org/files/{book_id}/{book_id}-h.htm",
        f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.html",
    ]


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    body = soup.body or soup
    text = body.get_text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines()]
    norm = []
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


def has_preface_info(prefix_text: str) -> bool:
    low = prefix_text.lower()
    return any(hint.lower() in low for hint in PREFACE_HINTS)


def fetch_html_with_preface(book_id: str):
    for url in build_html_urls(book_id):
        try:
            r = requests.get(url, timeout=TIMEOUT, headers=HEADERS)
            if r.status_code != 200 or len(r.content) < 2000:
                continue
            text_all = html_to_text(r.text)
            m = START_RE.search(text_all)
            preface = text_all[: m.start()] if m else text_all[:1000]
            if has_preface_info(preface):
                return text_all, url
        except requests.RequestException:
            continue
    return None, None


def extract_body_for_counting(text: str) -> str:
    lic_m = LICENSE_RE.search(text)
    cut = text[: lic_m.start()] if lic_m else text
    start_m = START_RE.search(cut)
    body = cut[start_m.end() :] if start_m else cut
    end_m = END_RE.search(body)
    if end_m:
        body = body[: end_m.start()]
    return body.strip()


def count_words(s: str) -> int:
    return len(WORD_RE.findall(s))


def append_meta(meta_writer, book_id, row, wc, url):
    meta_writer.writerow(
        {
            "Text#": book_id,
            "Title": row.get("Title", ""),
            "Authors": row.get("Authors", ""),
            "Language": row.get("Language", ""),
            "Issued": row.get("Issued", ""),
            "URL": url,
            "Words": wc,
        }
    )


def main():
    ensure_dir(DEST_FULL)
    catalog = download_catalog_if_needed()
    rows = iter_english_rows(catalog)

    new_file = not META_CSV.exists()
    meta_f = open(META_CSV, "a", newline="", encoding="utf-8")
    meta_writer = csv.DictWriter(
        meta_f,
        fieldnames=["Text#", "Title", "Authors", "Language", "Issued", "URL", "Words"],
    )
    if new_file:
        meta_writer.writeheader()

    kept = seen = 0
    print(
        f"Objectif : conserver {COUNT_TARGET} ouvrages (texte ≥{MIN_WORDS} mots et informations préliminaires complètes)."
    )

    for row in rows:
        if kept >= COUNT_TARGET:
            break
        seen += 1

        book_id = row["Text#"].strip()
        title = row.get("Title", "")[:80]

        out_path = DEST_FULL / f"{book_id}.txt"
        if out_path.exists():
            print(f"[SKIP-EXIST] {book_id}  {title}")
            kept += 1
            continue

        text_all, used_url = fetch_html_with_preface(book_id)
        if not text_all:
            print(f"[MISS] {book_id}  {title}")
            continue

        body = extract_body_for_counting(text_all)
        wc = count_words(body)

        if wc >= MIN_WORDS:
            out_path.write_text(text_all, encoding="utf-8")
            append_meta(meta_writer, book_id, row, wc, used_url)
            kept += 1
            print(f"[KEEP] {book_id}  words={wc}  src={used_url}")
        else:
            print(f"[DROP] {book_id}  words={wc}  src={used_url}")

    meta_f.close()
    print(f"\nTerminé : conservé {kept}/{COUNT_TARGET} ouvrages (sur {seen} examinés).")
    print(f"Répertoire de sauvegarde : {DEST_FULL}")
    print(f"Fichier de métadonnées : {META_CSV}")


if __name__ == "__main__":
    main()
