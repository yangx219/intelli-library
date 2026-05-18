#!/usr/bin/env python3
"""
Rebuild db_index.sqlite3 using the same steps as library/index_full_build.sh (Windows-friendly).

Run from repo root (uses the same Python as this interpreter for Django commands):

  python scripts/build_index_pipeline.py --fresh-db
  python scripts/build_index_pipeline.py --index-limit 100

Requires: deps installed from library/requirements.txt and NLTK Porter data (usually auto).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "library"
META = ROOT / "data" / "selected_meta.csv"
BOOKS = ROOT / "books_html_kept"
DB = LIBRARY / "db_index.sqlite3"


def run_manage(py: str, *args: str) -> None:
    cmd = [py, str(LIBRARY / "manage.py"), *args]
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    print("+", " ".join(cmd), flush=True)
    subprocess.check_call(cmd, cwd=str(LIBRARY), env=env)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh-db", action="store_true", help="Delete library/db_index.sqlite3 before migrate")
    ap.add_argument(
        "--index-limit",
        type=int,
        default=0,
        help="Forward to index_build_fast --limit (0 = all rows in CSV that have .txt)",
    )
    args = ap.parse_args()

    py = sys.executable

    if not META.exists():
        print(f"Missing {META}", file=sys.stderr)
        return 1
    if not BOOKS.is_dir():
        print(f"Missing corpus dir {BOOKS} — run scripts/fetch_books_from_selected_meta.py first.", file=sys.stderr)
        return 1

    n_files = sum(
        1 for p in BOOKS.iterdir() if p.is_file() and p.suffix.lower() in (".txt", ".html", ".htm")
    )
    if n_files == 0:
        print(f"No .txt/.html/.htm files in {BOOKS}", file=sys.stderr)
        return 1
    print(f"Found {n_files} corpus files (.txt/.html/.htm) under {BOOKS}")

    if args.fresh_db and DB.exists():
        DB.unlink()
        print(f"Removed {DB}")

    run_manage(py, "migrate", "--settings=library.settings_index", "--noinput")

    fast_args = [
        "index_build_fast",
        "--settings=library.settings_index",
        "--meta",
        str(META),
        "--dir",
        str(BOOKS),
        "--topk",
        "7000",
    ]
    if args.index_limit > 0:
        fast_args.extend(["--limit", str(args.index_limit)])

    run_manage(py, *fast_args)

    run_manage(py, "index_compute_tfidf", "--settings=library.settings_index")
    run_manage(py, "index_prune_tfidf", "--settings=library.settings_index", "--topk", "2500")
    run_manage(py, "build_doc_vectors", "--settings=library.settings_index")
    run_manage(py, "build_doc_graph", "--settings=library.settings_index")
    run_manage(py, "compute_centrality", "--settings=library.settings_index")

    print("\nFinished. SQLite database:", DB)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
