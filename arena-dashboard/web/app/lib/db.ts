import Database from 'better-sqlite3';
import path from 'path';

let db: Database.Database | null = null;

export function getDb() {
  if (!db) {
    const dbPath = process.env.DATABASE_PATH || path.join(process.cwd(), '../../data/app.db');
    db = new Database(dbPath, { readonly: true });
    db.pragma('journal_mode = WAL');
  }
  return db;
}
