import Database, { Database as DB } from 'better-sqlite3';
import fs from 'fs';
import path from 'path';

const CANONICAL_SCHEMA_VERSION = 4;
const localEventsDb = path.join(process.cwd(), '../../events.db');
const localAppDb = path.join(process.cwd(), '../data/app.db');

const dbPath = process.env.DATABASE_PATH || (fs.existsSync(localEventsDb) ? localEventsDb : localAppDb);

let db: DB | null = null;

function assertCanonicalSchema(database: DB) {
  const migration = database
    .prepare("SELECT max(version) AS version FROM schema_migrations")
    .get() as { version: number | null } | undefined;
  const version = Number(migration?.version ?? 0);
  if (version < CANONICAL_SCHEMA_VERSION) {
    throw new Error(
      `SQLite schema version ${version} is not supported. Run: python migrate_db.py --database ${dbPath}`,
    );
  }
}

if (process.env.npm_lifecycle_event !== 'build') {
  try {
    db = new Database(dbPath);
    db.pragma('foreign_keys = ON');
    db.pragma('journal_mode = WAL');
    assertCanonicalSchema(db);
  } catch (error) {
    console.error('Blad polaczenia z kanoniczna baza SQLite:', error);
    db = null;
  }
}

export default db;
