#!/usr/bin/env python3
"""Restore a SQLite backup after services using the database have been stopped."""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Restore a SQLite database backup.")
    parser.add_argument("--backup", required=True, help="Backup database file to restore.")
    parser.add_argument("--database", required=True, help="Target database path, for example /data/app.db.")
    parser.add_argument("--emergency-dir", required=True, help="Directory for a pre-rollback emergency copy.")
    return parser.parse_args()


def integrity_check(path: Path) -> str:
    conn = sqlite3.connect(str(path))
    try:
        return str(conn.execute("PRAGMA integrity_check").fetchone()[0])
    finally:
        conn.close()


def main() -> int:
    args = parse_args()
    backup = Path(args.backup).expanduser()
    database = Path(args.database).expanduser()
    emergency_dir = Path(args.emergency_dir).expanduser()

    if not backup.exists():
        print(f"Backup does not exist: {backup}", file=sys.stderr)
        return 2
    if not database.exists():
        print(f"Target database does not exist: {database}", file=sys.stderr)
        return 2
    if backup.resolve() == database.resolve():
        print("Backup and target database must be different paths.", file=sys.stderr)
        return 2

    check = integrity_check(backup)
    if check != "ok":
        print(f"Refusing to restore backup with failed integrity_check: {check}", file=sys.stderr)
        return 1

    emergency_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    emergency = emergency_dir / f"pre-rollback-{timestamp}.db"

    shutil.copy2(database, emergency)
    shutil.copy2(backup, database)

    for sidecar in [Path(f"{database}-wal"), Path(f"{database}-shm")]:
        if sidecar.exists():
            os.remove(sidecar)

    print(f"Emergency copy: {emergency}")
    print(f"Restored backup: {backup}")
    print(f"Restored database: {database}")
    print("integrity_check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
