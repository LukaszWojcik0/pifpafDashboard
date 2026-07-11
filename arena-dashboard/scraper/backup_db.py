#!/usr/bin/env python3
"""Create and verify a consistent SQLite backup using the SQLite Backup API."""

from __future__ import annotations

import argparse
from contextlib import closing
import json
import os
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a consistent SQLite backup.")
    parser.add_argument("--source", required=True, help="SQLite database path, for example /data/app.db.")
    parser.add_argument("--dest", help="Exact backup file path to create.")
    parser.add_argument("--dest-dir", help="Directory for timestamped backup file.")
    parser.add_argument("--pages", type=int, default=1000, help="Pages copied per backup step.")
    return parser.parse_args()


def sqlite_uri(path: Path) -> str:
    return f"file:{path.resolve().as_posix()}?mode=ro"


def backup_destination(args: argparse.Namespace) -> Path:
    if bool(args.dest) == bool(args.dest_dir):
        raise SystemExit("Provide exactly one of --dest or --dest-dir.")
    if args.dest:
        return Path(args.dest).expanduser()
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return Path(args.dest_dir).expanduser() / f"app-{timestamp}.db"


def integrity_check(path: Path) -> str:
    with closing(sqlite3.connect(str(path))) as conn:
        row = conn.execute("PRAGMA integrity_check").fetchone()
    return str(row[0]) if row else "no result"


def main() -> int:
    args = parse_args()
    source = Path(args.source).expanduser()
    dest = backup_destination(args)
    temp_dest = Path(f"{dest}.tmp")
    metadata_path = Path(f"{dest}.metadata.json")

    if not source.exists():
        print(f"Source database does not exist: {source}", file=sys.stderr)
        return 2
    if source.resolve() == dest.resolve():
        print("Source and destination must be different paths.", file=sys.stderr)
        return 2

    dest.parent.mkdir(parents=True, exist_ok=True)

    existing = [path for path in [dest, temp_dest, metadata_path] if path.exists()]
    if existing:
        print("Refusing to overwrite existing backup-related files:", file=sys.stderr)
        for path in existing:
            print(f"  {path}", file=sys.stderr)
        return 3

    started_at = datetime.now(UTC).isoformat()
    try:
        with closing(sqlite3.connect(sqlite_uri(source), uri=True, timeout=30)) as src:
            with closing(sqlite3.connect(str(temp_dest))) as dst:
                src.backup(dst, pages=args.pages)

        integrity = integrity_check(temp_dest)
        if integrity != "ok":
            raise RuntimeError(f"integrity_check failed: {integrity}")

        os.replace(temp_dest, dest)
        metadata_path.write_text(
            json.dumps(
                {
                    "source": str(source),
                    "destination": str(dest),
                    "created_at_utc": started_at,
                    "sqlite_version": sqlite3.sqlite_version,
                    "integrity_check": integrity,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
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
