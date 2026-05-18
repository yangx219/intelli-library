#!/usr/bin/env python3
"""
Pack library/db_index.sqlite3 (+ manifest) into a zip you can copy to another PC or cloud drive.

Usage (repo root):

  python scripts/backup_index.py
  python scripts/backup_index.py --out D:\\Backups\\ibe-index.zip

Git ignores db_index.sqlite3 — cloning/pulling the repo never restores it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "library" / "db_index.sqlite3"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB, help="Path to db_index.sqlite3")
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output zip path (default: repo root ibe-index-YYYYMMDD-HHMMSS.zip)",
    )
    args = ap.parse_args()

    db = Path(args.db).resolve()
    if not db.is_file():
        print(f"Nothing to backup — missing database:\n  {db}", file=sys.stderr)
        print("Build it first: python scripts/build_index_pipeline.py", file=sys.stderr)
        return 1

    out = args.out
    if out is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
        out = ROOT / f"ibe-index-{stamp}.zip"
    else:
        out = Path(out).resolve()

    out.parent.mkdir(parents=True, exist_ok=True)

    digest = hashlib.sha256()
    with db.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    sha256_hex = digest.hexdigest()

    manifest = {
        "schema_version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "paths_relative_to_repo": {
            "sqlite": "library/db_index.sqlite3",
        },
        "sha256_db_index_sqlite": sha256_hex,
        "notes": (
            "This archive restores search/PageRank only. For full reproducibility also copy "
            "`books_html_kept/` and `data/selected_meta.csv`, or rebuild via scripts/build_index_pipeline.py."
        ),
    }

    arc_prefix = "intelli-book-index-bundle/"
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.write(db, arc_prefix + "library/db_index.sqlite3")
        z.writestr(
            arc_prefix + "IBE_MANIFEST.json",
            json.dumps(manifest, indent=2) + "\n",
        )

    print("Created:", out)
    print("SHA256 of SQLite:", sha256_hex)
    print("Restore on another machine: python scripts/restore_index.py", repr(str(out)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
