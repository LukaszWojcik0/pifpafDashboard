import Database from 'better-sqlite3';
import path from 'path';
import fs from 'fs';

// W kontenerze używamy zmiennej env. Na lokalnych środowiskach fallback do katalogu z aplikacją
const dbPath = process.env.DATABASE_PATH || path.join(process.cwd(), '../data/app.db');

const initDB = () => {
  // Zabezpieczenie na czas budowania obrazu (npm run build), gdy folder z bazą nie istnieje
  if (process.env.NODE_ENV === 'production' && !fs.existsSync(dbPath)) {
    return new Database(':memory:');
  }
  const instance = new Database(dbPath, { readonly: true });
  // WAL mode upewnia nas o bezkonfliktowym jednoczesnym odczycie (web) i zapisie (scraper)
  instance.pragma('journal_mode = WAL');
  return instance;
};

const db = initDB();

export default db;