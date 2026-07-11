import argparse
import json
import os
import shutil
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

CANONICAL_SCHEMA_VERSION = 4

MIGRATIONS = [
    (1, "001_create_canonical_schema"),
    (2, "002_migrate_legacy_scraper_schema"),
    (3, "003_migrate_legacy_web_schema"),
    (4, "004_add_constraints_indexes_status"),
]

VALID_STATUSES = {"available", "sold_out", "unknown"}


class UnsupportedSchemaError(RuntimeError):
    pass


@dataclass
class MigrationReport:
    schema_kind: str
    dry_run: bool = False
    migrated_events: int = 0
    migrated_snapshots: int = 0
    migrated_sources: int = 0
    migrated_users: int = 0
    migrated_sessions: int = 0
    skipped_duplicate_events: int = 0
    skipped_orphan_snapshots: int = 0
    applied_migrations: list[str] = field(default_factory=list)
    integrity_check: str | None = None
    foreign_key_issues: int = 0

    def as_dict(self):
        return {
            "schema_kind": self.schema_kind,
            "dry_run": self.dry_run,
            "migrated_events": self.migrated_events,
            "migrated_snapshots": self.migrated_snapshots,
            "migrated_sources": self.migrated_sources,
            "migrated_users": self.migrated_users,
            "migrated_sessions": self.migrated_sessions,
            "skipped_duplicate_events": self.skipped_duplicate_events,
            "skipped_orphan_snapshots": self.skipped_orphan_snapshots,
            "applied_migrations": self.applied_migrations,
            "schema_version": CANONICAL_SCHEMA_VERSION,
            "integrity_check": self.integrity_check,
            "foreign_key_issues": self.foreign_key_issues,
        }


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_timestamp(value) -> str:
    if not value:
        return utc_now()
    text = str(value).strip()
    if text.endswith("Z"):
        return text
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except ValueError:
        return text


def connect_database(path: str) -> sqlite3.Connection:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {row["name"] for row in rows if not row["name"].startswith("sqlite_")}


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    except sqlite3.OperationalError:
        return set()
    return {row["name"] for row in rows}


def has_table(conn: sqlite3.Connection, table: str) -> bool:
    return table in table_names(conn)


def is_empty_database(conn: sqlite3.Connection) -> bool:
    return not table_names(conn)


def schema_version(conn: sqlite3.Connection) -> int:
    if not has_table(conn, "schema_migrations"):
        return 0
    row = conn.execute("SELECT max(version) AS version FROM schema_migrations").fetchone()
    return int(row["version"] or 0)


def detect_schema_kind(conn: sqlite3.Connection) -> str:
    if is_empty_database(conn):
        return "empty"

    names = table_names(conn)
    event_cols = table_columns(conn, "events")
    snapshot_cols = table_columns(conn, "snapshots")
    legacy_snapshot_cols = table_columns(conn, "event_snapshots")

    if (
        {"schema_migrations", "events", "snapshots", "scraping_sources", "users", "sessions", "system_status"}.issubset(names)
        and {"url", "event_date", "event_time", "status", "current_available", "max_available"}.issubset(event_cols)
        and {"available", "status", "checked_at"}.issubset(snapshot_cols)
    ):
        return "canonical"

    if {"events", "event_snapshots"}.issubset(names) and {"link", "date_info"}.issubset(event_cols) and {"available_places", "timestamp"}.issubset(legacy_snapshot_cols):
        return "legacy_scraper"

    if {"events", "snapshots"}.issubset(names) and {"url", "event_date", "event_time", "status"}.issubset(event_cols) and {"available", "checked_at"}.issubset(snapshot_cols):
        return "legacy_web"

    if names.issubset({"schema_migrations", "users", "sessions", "scraping_sources", "system_status"}):
        return "partial"

    raise UnsupportedSchemaError(f"Unsupported SQLite schema. Existing tables: {', '.join(sorted(names))}")


def canonical_schema_sql() -> str:
    return """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        applied_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS scraping_sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        list_url TEXT NOT NULL,
        list_links_selector TEXT,
        title_selector TEXT,
        date_selector TEXT,
        time_selector TEXT,
        image_selector TEXT,
        tickets_regex TEXT,
        sold_out_regex TEXT,
        is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
        is_api INTEGER NOT NULL DEFAULT 0 CHECK (is_api IN (0, 1)),
        request_headers TEXT,
        ntfy_url TEXT,
        ntfy_template TEXT,
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
        updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
        UNIQUE(name, list_url)
    );

    CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY,
        source_id INTEGER REFERENCES scraping_sources(id) ON DELETE SET NULL,
        title TEXT NOT NULL,
        url TEXT NOT NULL UNIQUE,
        event_date TEXT,
        event_time TEXT,
        status TEXT NOT NULL DEFAULT 'unknown' CHECK (status IN ('available', 'sold_out', 'unknown')),
        current_available INTEGER CHECK (current_available IS NULL OR current_available >= 0),
        max_available INTEGER CHECK (max_available IS NULL OR max_available >= 0),
        last_seen TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
        updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
        image_url TEXT
    );

    CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
        available INTEGER CHECK (available IS NULL OR available >= 0),
        status TEXT NOT NULL CHECK (status IN ('available', 'sold_out', 'unknown')),
        checked_at TEXT NOT NULL,
        rejection_reason TEXT,
        UNIQUE(event_id, checked_at)
    );

    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
    );

    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        username TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
    );

    CREATE TABLE IF NOT EXISTS system_status (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
    );

    CREATE TABLE IF NOT EXISTS scraper_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        status TEXT NOT NULL CHECK (status IN ('running', 'success', 'failed', 'skipped')),
        summary_json TEXT,
        error TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_events_last_seen ON events(last_seen DESC);
    CREATE INDEX IF NOT EXISTS idx_events_source ON events(source_id);
    CREATE INDEX IF NOT EXISTS idx_snapshots_event_time ON snapshots(event_id, checked_at DESC);
    CREATE INDEX IF NOT EXISTS idx_scraping_sources_active ON scraping_sources(is_active);
    CREATE INDEX IF NOT EXISTS idx_scraper_runs_started ON scraper_runs(started_at DESC);
    """


def create_canonical_schema(conn: sqlite3.Connection) -> None:
    for statement in canonical_schema_sql().split(";"):
        sql = statement.strip()
        if sql:
            conn.execute(sql)


def record_migrations(conn: sqlite3.Connection, report: MigrationReport) -> None:
    now = utc_now()
    for version, name in MIGRATIONS:
        row = conn.execute("SELECT version FROM schema_migrations WHERE version = ?", (version,)).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                (version, name, now),
            )
            report.applied_migrations.append(name)


def rename_existing_tables(conn: sqlite3.Connection) -> None:
    for table in ["event_snapshots", "snapshots", "events", "scraping_sources", "sessions", "users", "system_status", "scraper_runs"]:
        if has_table(conn, table) and not has_table(conn, f"{table}_legacy_before_migration"):
            conn.execute(f"ALTER TABLE {table} RENAME TO {table}_legacy_before_migration")


def default_source_id(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT id FROM scraping_sources WHERE name = ? ORDER BY id LIMIT 1", ("Arena Walki",)).fetchone()
    if row:
        return int(row["id"])
    now = utc_now()
    cursor = conn.execute(
        """
        INSERT INTO scraping_sources
        (name, list_url, list_links_selector, title_selector, date_selector, time_selector, image_selector,
         tickets_regex, sold_out_regex, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "Arena Walki",
            "https://arenawalki.pl/gry-otwarte/",
            'a[href*="/produkt/"], a[href*="/wydarzenie/"], a[href*="/events/"]',
            "h1",
            '[class*="date"], [class*="data"]',
            '[class*="time"], [class*="czas"], [class*="godzina"]',
            'meta[property="og:image"], .wp-post-image, .woocommerce-product-gallery__image img',
            r"\((\d+)\s+dost(?:epnych|ępnych)\)",
            r"wyprzedane|brak biletow|brak biletów|brak w magazynie|sprzedaz zamknieta|sprzedaż zamknięta",
            now,
            now,
        ),
    )
    return int(cursor.lastrowid)


def normalize_status(raw, available=None) -> str:
    text = (str(raw or "")).lower()
    if raw in VALID_STATUSES:
        return raw
    if available == 0 or "wyprzed" in text or "sold" in text or "closed" in text:
        return "sold_out"
    if available is not None or "dost" in text or "available" in text:
        return "available"
    return "unknown"


def copy_sources(conn: sqlite3.Connection, report: MigrationReport) -> None:
    if not has_table(conn, "scraping_sources_legacy_before_migration"):
        default_source_id(conn)
        return

    cols = table_columns(conn, "scraping_sources_legacy_before_migration")
    rows = conn.execute("SELECT * FROM scraping_sources_legacy_before_migration ORDER BY id").fetchall()
    now = utc_now()
    for row in rows:
        values = {key: row[key] if key in cols else None for key in cols}
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO scraping_sources
            (id, name, list_url, list_links_selector, title_selector, date_selector, time_selector, image_selector,
             tickets_regex, sold_out_regex, is_active, is_api, request_headers, ntfy_url, ntfy_template, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                values.get("id"),
                values.get("name") or "Imported source",
                values.get("list_url") or "https://example.invalid/",
                values.get("list_links_selector"),
                values.get("title_selector"),
                values.get("date_selector"),
                values.get("time_selector"),
                values.get("image_selector"),
                values.get("tickets_regex"),
                values.get("sold_out_regex"),
                int(values.get("is_active") if values.get("is_active") is not None else 1),
                int(values.get("is_api") if values.get("is_api") is not None else 0),
                values.get("request_headers"),
                values.get("ntfy_url"),
                values.get("ntfy_template"),
                normalize_timestamp(values.get("created_at") if "created_at" in cols else now),
                normalize_timestamp(values.get("updated_at") if "updated_at" in cols else now),
            ),
        )
        report.migrated_sources += cursor.rowcount if cursor.rowcount > 0 else 0

    if not conn.execute("SELECT 1 FROM scraping_sources LIMIT 1").fetchone():
        default_source_id(conn)


def copy_users_and_sessions(conn: sqlite3.Connection, report: MigrationReport) -> None:
    now = utc_now()
    if has_table(conn, "users_legacy_before_migration"):
        cols = table_columns(conn, "users_legacy_before_migration")
        for row in conn.execute("SELECT * FROM users_legacy_before_migration").fetchall():
            cursor = conn.execute(
                "INSERT OR IGNORE INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
                (
                    row["username"],
                    row["password_hash"],
                    row["salt"],
                    normalize_timestamp(row["created_at"] if "created_at" in cols else now),
                ),
            )
            report.migrated_users += cursor.rowcount if cursor.rowcount > 0 else 0

    if has_table(conn, "sessions_legacy_before_migration"):
        cols = table_columns(conn, "sessions_legacy_before_migration")
        for row in conn.execute("SELECT * FROM sessions_legacy_before_migration").fetchall():
            if not conn.execute("SELECT 1 FROM users WHERE username = ?", (row["username"],)).fetchone():
                continue
            cursor = conn.execute(
                "INSERT OR IGNORE INTO sessions (token, username, expires_at, created_at) VALUES (?, ?, ?, ?)",
                (
                    row["token"],
                    row["username"],
                    normalize_timestamp(row["expires_at"]),
                    normalize_timestamp(row["created_at"] if "created_at" in cols else now),
                ),
            )
            report.migrated_sessions += cursor.rowcount if cursor.rowcount > 0 else 0


def copy_status(conn: sqlite3.Connection) -> None:
    if not has_table(conn, "system_status_legacy_before_migration"):
        return
    cols = table_columns(conn, "system_status_legacy_before_migration")
    for row in conn.execute("SELECT * FROM system_status_legacy_before_migration").fetchall():
        conn.execute(
            """
            INSERT INTO system_status (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (
                row["key"],
                str(row["value"] if row["value"] is not None else ""),
                normalize_timestamp(row["updated_at"] if "updated_at" in cols else utc_now()),
            ),
        )


def legacy_snapshot_table(conn: sqlite3.Connection) -> str | None:
    if has_table(conn, "snapshots_legacy_before_migration"):
        return "snapshots_legacy_before_migration"
    if has_table(conn, "event_snapshots_legacy_before_migration"):
        return "event_snapshots_legacy_before_migration"
    return None


def latest_snapshot_values(conn: sqlite3.Connection, snapshot_table: str | None) -> dict[str, tuple[int | None, str | None]]:
    if not snapshot_table:
        return {}
    cols = table_columns(conn, snapshot_table)
    available_col = "available" if "available" in cols else "available_places"
    time_col = "checked_at" if "checked_at" in cols else "timestamp"
    rows = conn.execute(f"SELECT event_id, {available_col} AS available, {time_col} AS checked_at FROM {snapshot_table} ORDER BY {time_col}, id").fetchall()
    latest = {}
    for row in rows:
        latest[row["event_id"]] = (row["available"], normalize_timestamp(row["checked_at"]))
    return latest


def copy_events_and_snapshots(conn: sqlite3.Connection, report: MigrationReport) -> None:
    if not has_table(conn, "events_legacy_before_migration"):
        return

    event_cols = table_columns(conn, "events_legacy_before_migration")
    snapshot_table = legacy_snapshot_table(conn)
    latest = latest_snapshot_values(conn, snapshot_table)
    default_source = default_source_id(conn)
    old_to_new: dict[str, str] = {}
    seen_urls: dict[str, str] = {}

    order_columns = [column for column in ["created_at", "last_seen", "id"] if column in event_cols]
    order_sql = ", ".join(order_columns) if order_columns else "rowid"
    rows = conn.execute(f"SELECT * FROM events_legacy_before_migration ORDER BY {order_sql}").fetchall()
    for row in rows:
        old_id = str(row["id"])
        url = row["url"] if "url" in event_cols else row["link"] if "link" in event_cols else None
        if not url:
            report.skipped_duplicate_events += 1
            continue
        if url in seen_urls:
            old_to_new[old_id] = seen_urls[url]
            report.skipped_duplicate_events += 1
            continue

        current_available, latest_seen = latest.get(old_id, (None, None))
        max_available = row["max_available"] if "max_available" in event_cols else current_available
        if max_available is None and current_available is not None:
            max_available = current_available
        status = normalize_status(row["status"] if "status" in event_cols else None, current_available)
        last_seen = normalize_timestamp(row["last_seen"] if "last_seen" in event_cols else latest_seen)
        created_at = normalize_timestamp(row["created_at"] if "created_at" in event_cols else last_seen)

        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO events
            (id, source_id, title, url, event_date, event_time, status, current_available, max_available,
             last_seen, created_at, updated_at, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                old_id,
                row["source_id"] if "source_id" in event_cols else default_source,
                row["title"] or "Untitled event",
                url,
                row["event_date"] if "event_date" in event_cols else row["date_info"] if "date_info" in event_cols else None,
                row["event_time"] if "event_time" in event_cols else "",
                status,
                current_available,
                max_available,
                last_seen,
                created_at,
                last_seen,
                row["image_url"] if "image_url" in event_cols else None,
            ),
        )
        if cursor.rowcount > 0:
            report.migrated_events += 1
        old_to_new[old_id] = old_id
        seen_urls[url] = old_id

    if snapshot_table:
        snapshot_cols = table_columns(conn, snapshot_table)
        available_col = "available" if "available" in snapshot_cols else "available_places"
        time_col = "checked_at" if "checked_at" in snapshot_cols else "timestamp"
        status_col = "status" if "status" in snapshot_cols else None
        for row in conn.execute(f"SELECT * FROM {snapshot_table} ORDER BY {time_col}, id").fetchall():
            mapped_event_id = old_to_new.get(str(row["event_id"]))
            if not mapped_event_id:
                report.skipped_orphan_snapshots += 1
                continue
            available = row[available_col]
            checked_at = normalize_timestamp(row[time_col])
            status = normalize_status(row[status_col] if status_col else None, available)
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO snapshots (event_id, available, status, checked_at)
                VALUES (?, ?, ?, ?)
                """,
                (mapped_event_id, available, status, checked_at),
            )
            if cursor.rowcount > 0:
                report.migrated_snapshots += 1

    for row in conn.execute("SELECT id, max_available FROM events").fetchall():
        latest = conn.execute(
            """
            SELECT available, status, checked_at
            FROM snapshots
            WHERE event_id = ?
            ORDER BY checked_at DESC, id DESC
            LIMIT 1
            """,
            (row["id"],),
        ).fetchone()
        if not latest:
            continue
        max_seen = conn.execute(
            "SELECT max(available) AS value FROM snapshots WHERE event_id = ?",
            (row["id"],),
        ).fetchone()["value"]
        max_available = max(row["max_available"] or 0, max_seen or 0)
        conn.execute(
            """
            UPDATE events
            SET current_available = ?, status = ?, max_available = ?, last_seen = ?, updated_at = ?
            WHERE id = ?
            """,
            (latest["available"], latest["status"], max_available, latest["checked_at"], latest["checked_at"], row["id"]),
        )


def validate_before_migration(conn: sqlite3.Connection) -> None:
    result = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        raise RuntimeError(f"SQLite integrity_check failed before migration: {result}")


def validate_after_migration(conn: sqlite3.Connection, report: MigrationReport) -> None:
    result = conn.execute("PRAGMA integrity_check").fetchone()[0]
    fk_issues = conn.execute("PRAGMA foreign_key_check").fetchall()
    report.integrity_check = result
    report.foreign_key_issues = len(fk_issues)
    if result != "ok":
        raise RuntimeError(f"SQLite integrity_check failed after migration: {result}")
    if fk_issues:
        raise RuntimeError(f"SQLite foreign_key_check found {len(fk_issues)} issue(s)")


def plan_migration(conn: sqlite3.Connection) -> MigrationReport:
    kind = detect_schema_kind(conn)
    report = MigrationReport(schema_kind=kind, dry_run=True)
    if kind == "canonical" and schema_version(conn) >= CANONICAL_SCHEMA_VERSION:
        return report
    report.applied_migrations = [name for _, name in MIGRATIONS if schema_version(conn) < CANONICAL_SCHEMA_VERSION]
    return report


def migrate_connection(conn: sqlite3.Connection, dry_run: bool = False) -> MigrationReport:
    validate_before_migration(conn)
    if dry_run:
        return plan_migration(conn)

    kind = detect_schema_kind(conn)
    report = MigrationReport(schema_kind=kind)

    if kind == "canonical" and schema_version(conn) >= CANONICAL_SCHEMA_VERSION:
        validate_after_migration(conn, report)
        return report

    conn.execute("BEGIN IMMEDIATE")
    try:
        if kind != "empty" and kind != "canonical":
            rename_existing_tables(conn)
        create_canonical_schema(conn)
        if kind != "empty":
            copy_sources(conn, report)
            copy_users_and_sessions(conn, report)
            copy_status(conn)
            copy_events_and_snapshots(conn, report)
        else:
            default_source_id(conn)
        record_migrations(conn, report)
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    validate_after_migration(conn, report)
    return report


def migrate_database(path: str, dry_run: bool = False) -> MigrationReport:
    conn = connect_database(path)
    try:
        return migrate_connection(conn, dry_run=dry_run)
    finally:
        conn.close()


def restore_backup(backup_path: str, database_path: str) -> None:
    if not os.path.exists(backup_path):
        raise FileNotFoundError(backup_path)
    if os.path.abspath(backup_path) == os.path.abspath(database_path):
        raise ValueError("Backup path and database path must be different")
    shutil.copy2(backup_path, database_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan or run the pifpafDashboard SQLite migration.")
    parser.add_argument("--database", required=True, help="Explicit path to the SQLite database file.")
    parser.add_argument("--dry-run", action="store_true", help="Only print the detected plan; do not write.")
    parser.add_argument("--check", action="store_true", help="Validate the migrated database after running or planning.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")
    args = parser.parse_args()

    db_path = Path(args.database)
    if not db_path.exists() and not args.dry_run:
        db_path.parent.mkdir(parents=True, exist_ok=True)

    report = migrate_database(str(db_path), dry_run=args.dry_run)
    payload = report.as_dict()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        mode = "Migration plan" if args.dry_run else "Migration completed"
        print(f"{mode}: {args.database}")
        print(f"schema_kind: {report.schema_kind}")
        print(f"schema_version: {CANONICAL_SCHEMA_VERSION}")
        if report.applied_migrations:
            print("migrations: " + ", ".join(report.applied_migrations))
        else:
            print("migrations: none")
        if not args.dry_run:
            print(f"events: {report.migrated_events}")
            print(f"snapshots: {report.migrated_snapshots}")
            print(f"sources: {report.migrated_sources}")
            print(f"users: {report.migrated_users}")
            print(f"sessions: {report.migrated_sessions}")
            print(f"duplicates_skipped: {report.skipped_duplicate_events}")
            print(f"orphan_snapshots_skipped: {report.skipped_orphan_snapshots}")
            print(f"integrity_check: {report.integrity_check}")
            print(f"foreign_key_issues: {report.foreign_key_issues}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
