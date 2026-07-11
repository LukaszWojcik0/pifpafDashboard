#!/usr/bin/env python3
"""Create and verify a SQLite backup using the SQLite Backup API.

This helper is intentionally conservative:
- source and destination paths must be provided explicitly;
- existing backup files are not overwritten unless the operator confirms it;
- the produced copy is checked with PRAGMA integrity_check.
"""

from __future__ import annotations

import argparse
from contextlib import closing
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a consistent SQLite backup, including databases using WAL mode."
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Explicit path to the source SQLite database, for example /data/app.db.",
    )
    parser.add_argument(
        "--dest",
        required=True,
        help="Explicit path for the backup database to create.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwrite only after an interactive confirmation prompt.",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=1000,
        help="Pages copied per backup step. Default: 1000.",
    )
    return parser.parse_args()


def sidecar_paths(db_path: Path) -> list[Path]:
    return [db_path, Path(f"{db_path}-wal"), Path(f"{db_path}-shm")]


def confirm_overwrite(paths: list[Path]) -> None:
    existing = [path for path in paths if path.exists()]
    if not existing:
        return

    print("The following destination files already exist:", file=sys.stderr)
    for path in existing:
        print(f"  {path}", file=sys.stderr)
    answer = input("Type OVERWRITE to replace them: ")
    if answer != "OVERWRITE":
        raise SystemExit("Refusing to overwrite existing backup files.")

    for path in existing:
        path.unlink()


def sqlite_uri(path: Path) -> str:
    resolved = path.resolve()
    return f"file:{resolved.as_posix()}?mode=ro"


def run_integrity_check(db_path: Path) -> str:
    with closing(sqlite3.connect(str(db_path))) as conn:
        row = conn.execute("PRAGMA integrity_check;").fetchone()
    return str(row[0]) if row else "no result"


def main() -> int:
    args = parse_args()
    source = Path(args.source).expanduser()
    dest = Path(args.dest).expanduser()
    metadata_path = Path(f"{dest}.metadata.json")
    temp_dest = Path(f"{dest}.tmp")

    if not source.exists():
        print(f"Source database does not exist: {source}", file=sys.stderr)
        return 2
    if source.resolve() == dest.resolve():
        print("Source and destination must be different paths.", file=sys.stderr)
        return 2

    dest.parent.mkdir(parents=True, exist_ok=True)

    destination_files = sidecar_paths(dest) + [metadata_path, temp_dest]
    existing = [path for path in destination_files if path.exists()]
    if existing and not args.overwrite:
        print("Refusing to overwrite existing backup-related files:", file=sys.stderr)
        for path in existing:
            print(f"  {path}", file=sys.stderr)
        print("Use --overwrite and confirm interactively if replacement is intended.", file=sys.stderr)
        return 3
    if args.overwrite:
        confirm_overwrite(destination_files)

    if temp_dest.exists():
        temp_dest.unlink()

    started_at = datetime.now(timezone.utc).isoformat()
    try:
        with closing(sqlite3.connect(sqlite_uri(source), uri=True, timeout=30)) as src:
            with closing(sqlite3.connect(str(temp_dest))) as dst:
                src.backup(dst, pages=args.pages)

        integrity = run_integrity_check(temp_dest)
        if integrity != "ok":
            raise RuntimeError(f"integrity_check failed: {integrity}")

        os.replace(temp_dest, dest)
        metadata = {
            "source": str(source),
            "destination": str(dest),
            "created_at_utc": started_at,
            "sqlite_version": sqlite3.sqlite_version,
            "integrity_check": integrity,
        }
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    except Exception as exc:
        if temp_dest.exists():
            temp_dest.unlink()
        print(f"Backup failed: {exc}", file=sys.stderr)
        return 1

    print(f"Backup created: {dest}")
    print("integrity_check: ok")
    print(f"Metadata written: {metadata_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
