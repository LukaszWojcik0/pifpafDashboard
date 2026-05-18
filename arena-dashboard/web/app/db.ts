import Database from 'better-sqlite3';
import path from 'path';

// W kontenerze używamy zmiennej env. Na lokalnych środowiskach fallback do katalogu z aplikacją
const dbPath = process.env.DATABASE_PATH || path.join(process.cwd(), '../data/app.db');
const db = new Database(dbPath, { readonly: true });

// WAL mode upewnia nas o bezkonfliktowym jednoczesnym odczycie (web) i zapisie (scraper)
db.pragma('journal_mode = WAL');

export default db;