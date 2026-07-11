#!/usr/bin/env python3
"""Validate a SQLite database with integrity and foreign-key checks."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check SQLite database integrity.")
    parser.add_argument("--database", required=True, help="SQLite database path.")
    parser.add_argument("--expect-schema-version", type=int, help="Expected schema_migrations max(version).")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    database = Path(args.database).expanduser()
    if not database.exists():
        print(f"Database does not exist: {database}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(str(database))
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = conn.execute("PRAGMA foreign_key_check").fetchall()
        print(f"Database checked: {database}")
        print(f"integrity_check: {integrity}")
        print(f"foreign_key_check: {foreign_keys}")
        if integrity != "ok":
            return 1

        if args.expect_schema_version is not None:
            row = conn.execute("SELECT max(version) FROM schema_migrations").fetchone()
            version = row[0] if row else None
            print(f"schema_version: {version}")
            if version != args.expect_schema_version:
                return 1
            if foreign_keys:
                return 1
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
