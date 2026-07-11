import json
import logging
import os
import re
import sqlite3
from datetime import UTC, datetime, timedelta

from db_migrations import (
    CANONICAL_SCHEMA_VERSION,
    connect_database,
    detect_schema_kind,
    migrate_connection,
    normalize_timestamp,
    schema_version,
)

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DATABASE_PATH", "app.db")


class SchemaMigrationRequired(RuntimeError):
    pass


def utc_now():
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def get_connection():
    return connect_database(DB_PATH)


def init_db():
    conn = get_connection()
    try:
        kind = detect_schema_kind(conn)
        version = schema_version(conn)
        if kind == "empty":
            report = migrate_connection(conn)
            logger.info("Created canonical database schema at %s: %s", DB_PATH, report.as_dict())
            return
        if kind == "canonical" and version >= CANONICAL_SCHEMA_VERSION:
            logger.info("Database schema is canonical at %s (version %s)", DB_PATH, version)
            return
        raise SchemaMigrationRequired(
            "Database schema requires a controlled migration. "
            f"Detected {kind} version {version}. Run migrate_db.py --database {DB_PATH} after backup."
        )
    finally:
        conn.close()


def update_status(key, value):
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO system_status (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, str(value), utc_now()),
        )
        conn.commit()
    finally:
        conn.close()


def sanitize_error_message(error):
    text = str(error or "unknown_error")
    text = re.sub(r"(?i)(authorization|cookie|api[_-]?key|token|password)=([^&\s]+)", r"\1=[redacted]", text)
    text = re.sub(r"(?i)(bearer|basic)\s+[a-z0-9._~+/=-]+", r"\1 [redacted]", text)
    return text[:500]


def _get_status(cursor, key):
    row = cursor.execute("SELECT value FROM system_status WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def _set_status(cursor, key, value):
    cursor.execute(
        """
        INSERT INTO system_status (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """,
        (key, str(value), utc_now()),
    )


def acquire_scrape_lease(owner, ttl_seconds=1800):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        now = datetime.now(UTC)
        expires_raw = _get_status(cursor, "scrape_lock_expires_at")
        current_owner = _get_status(cursor, "scrape_lock_owner")

        if expires_raw:
            try:
                expires_at = datetime.fromisoformat(expires_raw.replace("Z", "+00:00"))
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=UTC)
            except ValueError:
                expires_at = now - timedelta(seconds=1)
            if expires_at > now and current_owner and current_owner != owner:
                conn.rollback()
                return False

        expires_at = now + timedelta(seconds=ttl_seconds)
        _set_status(cursor, "scrape_lock_owner", owner)
        _set_status(cursor, "scrape_lock_expires_at", expires_at.isoformat().replace("+00:00", "Z"))
        conn.commit()
        return True
    finally:
        conn.close()


def release_scrape_lease(owner):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        current_owner = _get_status(cursor, "scrape_lock_owner")
        if current_owner == owner:
            _set_status(cursor, "scrape_lock_owner", "")
            _set_status(cursor, "scrape_lock_expires_at", "")
        conn.commit()
    finally:
        conn.close()


def start_scraper_run():
    conn = get_connection()
    now = utc_now()
    try:
        cursor = conn.execute(
            "INSERT INTO scraper_runs (started_at, status) VALUES (?, 'running')",
            (now,),
        )
        run_id = cursor.lastrowid
        conn.execute(
            """
            INSERT INTO system_status (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            ("last_scrape_started_at", now, now),
        )
        conn.execute(
            """
            INSERT INTO system_status (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            ("last_scrape_status", "running", now),
        )
        conn.commit()
        return run_id
    finally:
        conn.close()


def finish_scraper_run(run_id, status, summary=None, error=None):
    conn = get_connection()
    finished_at = utc_now()
    sanitized_error = sanitize_error_message(error) if error else None
    duration_seconds = None
    try:
        row = conn.execute("SELECT started_at FROM scraper_runs WHERE id = ?", (run_id,)).fetchone()
        if row and row["started_at"]:
            try:
                started_at = datetime.fromisoformat(str(row["started_at"]).replace("Z", "+00:00"))
                finished = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
                duration_seconds = max(0.0, (finished - started_at).total_seconds())
            except ValueError:
                duration_seconds = None
        conn.execute(
            """
            UPDATE scraper_runs
            SET finished_at = ?, status = ?, summary_json = ?, error = ?
            WHERE id = ?
            """,
            (finished_at, status, json.dumps(summary or {}, ensure_ascii=False), sanitized_error, run_id),
        )
        conn.commit()
    finally:
        conn.close()
    update_status("last_scrape_finished_at", finished_at)
    update_status("last_scrape_status", status)
    if duration_seconds is not None:
        update_status("last_scrape_duration_seconds", f"{duration_seconds:.3f}")
    if status == "success":
        update_status("last_success_at", finished_at)
    elif status == "failed":
        update_status("last_error_at", finished_at)
        update_status("last_error_reason", sanitized_error or "unknown_error")
    if summary is not None:
        update_status("last_scrape_summary", json.dumps(summary, ensure_ascii=False))


def split_date_info(date_info):
    value = (date_info or "").strip()
    if not value:
        return None, None
    parts = value.rsplit(" ", 1)
    if len(parts) == 2 and ":" in parts[1]:
        return parts[0], parts[1]
    return value, None


def event_status(available_places):
    if available_places is None:
        return "unknown"
    return "sold_out" if available_places == 0 else "available"


def update_event(event_id, title, link, date_info, available_places, image_url=None):
    """Insert/update an event and write a snapshot only for known changed values."""
    conn = get_connection()
    now = utc_now()
    event_date, event_time = split_date_info(date_info)
    measurement_known = available_places is not None
    status = event_status(available_places)

    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        row = cursor.execute(
            "SELECT current_available, max_available, created_at FROM events WHERE id = ?",
            (event_id,),
        ).fetchone()
        is_new = row is None
        previous_current = row["current_available"] if row else None
        previous_max = row["max_available"] if row else None
        max_available = previous_max
        current_available = previous_current

        if measurement_known:
            current_available = int(available_places)
            max_available = max(previous_max or 0, current_available)

        cursor.execute(
            """
            INSERT INTO events
            (id, title, url, event_date, event_time, status, current_available, max_available,
             last_seen, created_at, updated_at, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                url = excluded.url,
                event_date = excluded.event_date,
                event_time = excluded.event_time,
                status = excluded.status,
                current_available = excluded.current_available,
                max_available = excluded.max_available,
                last_seen = excluded.last_seen,
                updated_at = excluded.updated_at,
                image_url = excluded.image_url
            """,
            (
                event_id,
                title,
                link,
                event_date,
                event_time,
                status,
                current_available,
                max_available,
                now,
                normalize_timestamp(row["created_at"]) if row else now,
                now,
                image_url,
            ),
        )

        if measurement_known:
            latest = cursor.execute(
                """
                SELECT available, status
                FROM snapshots
                WHERE event_id = ?
                ORDER BY checked_at DESC, id DESC
                LIMIT 1
                """,
                (event_id,),
            ).fetchone()
            changed = latest is None or latest["available"] != current_available or latest["status"] != status
            if changed:
                cursor.execute(
                    """
                    INSERT INTO snapshots (event_id, available, status, checked_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (event_id, current_available, status, now),
                )

        conn.commit()
        return is_new, max_available, measurement_known
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
