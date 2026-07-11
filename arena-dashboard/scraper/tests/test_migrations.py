import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

SCRAPER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRAPER_DIR))

import db  # noqa: E402
from db_migrations import CANONICAL_SCHEMA_VERSION, migrate_database  # noqa: E402

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "db"


def fixture_sql(name):
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


class MigrationTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "test.db")

    def tearDown(self):
        self.tmpdir.cleanup()

    def load_fixture(self, name):
        if name == "empty.sql":
            sqlite3.connect(self.db_path).close()
            return
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(fixture_sql(name))
            conn.commit()
        finally:
            conn.close()

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def assert_integrity(self):
        conn = self.connect()
        try:
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
            version = conn.execute("SELECT max(version) FROM schema_migrations").fetchone()[0]
            self.assertEqual(version, CANONICAL_SCHEMA_VERSION)
        finally:
            conn.close()

    def test_empty_database_migration_and_rerun_are_idempotent(self):
        self.load_fixture("empty.sql")
        report = migrate_database(self.db_path)
        self.assertEqual(report.schema_kind, "empty")
        self.assert_integrity()

        second = migrate_database(self.db_path)
        self.assertEqual(second.schema_kind, "canonical")
        self.assertEqual(second.applied_migrations, [])
        self.assert_integrity()

    def test_historical_scraper_schema_migrates(self):
        self.load_fixture("historical_scraper.sql")
        report = migrate_database(self.db_path)
        self.assertEqual(report.schema_kind, "legacy_scraper")
        self.assertEqual(report.migrated_events, 1)
        self.assertEqual(report.migrated_snapshots, 1)
        self.assert_integrity()

        conn = self.connect()
        try:
            event = conn.execute("SELECT url, current_available, status FROM events WHERE id = 'legacy-1'").fetchone()
            self.assertEqual(event["url"], "https://arenawalki.pl/events/alpha")
            self.assertEqual(event["current_available"], 10)
            self.assertEqual(event["status"], "available")
            self.assertTrue(conn.execute("SELECT 1 FROM events_legacy_before_migration").fetchone())
        finally:
            conn.close()

    def test_historical_web_schema_migrates_users_sessions_and_snapshots(self):
        self.load_fixture("historical_web.sql")
        report = migrate_database(self.db_path)
        self.assertEqual(report.schema_kind, "legacy_web")
        self.assertEqual(report.migrated_users, 1)
        self.assertEqual(report.migrated_sessions, 1)
        self.assert_integrity()

        conn = self.connect()
        try:
            event = conn.execute("SELECT current_available, status FROM events WHERE id = 'web-1'").fetchone()
            self.assertEqual(event["current_available"], 18)
            self.assertEqual(event["status"], "available")
            self.assertEqual(conn.execute("SELECT count(*) FROM sessions").fetchone()[0], 1)
        finally:
            conn.close()

    def test_partial_database_migrates(self):
        self.load_fixture("partial.sql")
        report = migrate_database(self.db_path)
        self.assertEqual(report.schema_kind, "partial")
        self.assertEqual(report.migrated_users, 1)
        self.assertEqual(report.migrated_sessions, 1)
        self.assert_integrity()

    def test_duplicates_are_merged_without_breaking_unique_url(self):
        self.load_fixture("duplicates.sql")
        report = migrate_database(self.db_path)
        self.assertEqual(report.skipped_duplicate_events, 1)
        self.assert_integrity()

        conn = self.connect()
        try:
            self.assertEqual(conn.execute("SELECT count(*) FROM events").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT count(*) FROM snapshots").fetchone()[0], 2)
        finally:
            conn.close()

    def test_orphan_snapshots_are_reported_and_skipped(self):
        self.load_fixture("orphans.sql")
        report = migrate_database(self.db_path)
        self.assertEqual(report.skipped_orphan_snapshots, 1)
        self.assert_integrity()

        conn = self.connect()
        try:
            self.assertEqual(conn.execute("SELECT count(*) FROM snapshots").fetchone()[0], 1)
        finally:
            conn.close()

    def test_historical_timestamps_are_normalized_to_utc_iso(self):
        self.load_fixture("historical_timestamps.sql")
        migrate_database(self.db_path)
        self.assert_integrity()

        conn = self.connect()
        try:
            event = conn.execute("SELECT last_seen FROM events WHERE id = 'time-1'").fetchone()
            snapshot = conn.execute("SELECT checked_at FROM snapshots WHERE event_id = 'time-1'").fetchone()
            self.assertTrue(event["last_seen"].endswith("Z"))
            self.assertTrue(snapshot["checked_at"].endswith("Z"))
        finally:
            conn.close()

    def test_rollback_from_backup_restores_previous_file(self):
        self.load_fixture("historical_scraper.sql")
        backup_path = os.path.join(self.tmpdir.name, "backup.db")
        shutil.copy2(self.db_path, backup_path)

        migrate_database(self.db_path)
        shutil.copy2(backup_path, self.db_path)

        conn = self.connect()
        try:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            self.assertIn("event_snapshots", tables)
            self.assertNotIn("schema_migrations", tables)
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        finally:
            conn.close()

    def test_scraper_can_run_against_migrated_database(self):
        self.load_fixture("historical_scraper.sql")
        migrate_database(self.db_path)

        old_path = db.DB_PATH
        db.DB_PATH = self.db_path
        try:
            db.init_db()
            db.update_event("new-event", "New", "https://example.test/events/new", "2026-05-01 12:00", 3)
            conn = self.connect()
            try:
                self.assertEqual(conn.execute("SELECT count(*) FROM events").fetchone()[0], 2)
                self.assertEqual(conn.execute("SELECT count(*) FROM snapshots WHERE event_id = 'new-event'").fetchone()[0], 1)
            finally:
                conn.close()
        finally:
            db.DB_PATH = old_path


if __name__ == "__main__":
    unittest.main()
