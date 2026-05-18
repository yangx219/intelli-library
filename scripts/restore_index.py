#!/usr/bin/env python3
"""
Restore library/db_index.sqlite3 from a zip produced by scripts/backup_index.py.

Usage (repo root):

  python scripts/restore_index.py ibe-index-....zip
  python scripts/restore_index.py path/to/bundle.zip --force
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET_DB = ROOT / "library" / "db_index.sqlite3"


def _find_manifest_members(names: list[str]) -> tuple[str | None, str | None]:
    manifest_arc = None
    sqlite_arc = None
    for n in names:
        if n.endswith("IBE_MANIFEST.json"):
            manifest_arc = n
        if n.endswith("library/db_index.sqlite3"):
            sqlite_arc = n
    return manifest_arc, sqlite_arc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("zip_file", type=Path, help="Zip created by backup_index.py")
    ap.add_argument(
        "--force",
        action="store_true",
        help="Overwrite library/db_index.sqlite3 if it already exists",
    )
    args = ap.parse_args()

    zp = Path(args.zip_file).resolve()
    if not zp.is_file():
        print(f"Zip not found: {zp}", file=sys.stderr)
        return 1

    if TARGET_DB.exists() and not args.force:
        print(
            f"Refusing to overwrite existing DB:\n  {TARGET_DB}\n"
            "Pass --force to replace it.",
            file=sys.stderr,
        )
        return 1

    with zipfile.ZipFile(zp, "r") as z:
        names = z.namelist()
        manifest_arc, sqlite_arc = _find_manifest_members(names)
        if not sqlite_arc:
            print("Archive missing library/db_index.sqlite3 entry.", file=sys.stderr)
            return 1

        raw_sqlite = z.read(sqlite_arc)
        expected_sha = None
        if manifest_arc:
            try:
                manifest = json.loads(z.read(manifest_arc).decode("utf-8"))
                expected_sha = manifest.get("sha256_db_index_sqlite")
            except (json.JSONDecodeError, UnicodeDecodeError):
                expected_sha = None

        got = hashlib.sha256(raw_sqlite).hexdigest()
        if expected_sha and got != expected_sha:
            print(
                "SHA256 mismatch — archive may be corrupted.\n"
                f"  manifest: {expected_sha}\n"
                f"  actual:   {got}",
                file=sys.stderr,
            )
            return 1

        TARGET_DB.parent.mkdir(parents=True, exist_ok=True)
        TARGET_DB.write_bytes(raw_sqlite)

    try:
        con = sqlite3.connect(str(TARGET_DB))
        cur = con.cursor()
        cur.execute("PRAGMA quick_check")
        row = cur.fetchone()
        con.close()
        if not row or row[0] != "ok":
            print("SQLite quick_check did not return ok:", row, file=sys.stderr)
            return 1
    except sqlite3.Error as e:
        print("SQLite open/check failed:", e, file=sys.stderr)
        return 1

    print("Restored:", TARGET_DB)
    print("SHA256:", got)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
