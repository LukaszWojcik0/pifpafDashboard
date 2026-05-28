import Database, { Database as DB } from 'better-sqlite3';
import path from 'path';
import fs from 'fs';

const localEventsDb = path.join(process.cwd(), "../../events.db");
const fallbackDb = path.join(process.cwd(), "../data/app.db");

// Używamy pliku events.db z głównego katalogu (jeśli istnieje) lub app.db
const dbPath =
  process.env.DATABASE_PATH ||
  (fs.existsSync(localEventsDb) ? localEventsDb : fallbackDb);

let db: DB | null = null;

// Ta funkcja zapobiega próbie połączenia z plikiem bazy danych podczas procesu budowania (npm run build),
// kiedy plik fizycznie nie istnieje w kontenerze budującym.
if (process.env.npm_lifecycle_event !== 'build') {
  try {
    db = new Database(dbPath);
    db.pragma('journal_mode = WAL');

    // Inicjalizacja tabel autoryzacji
    db.exec(`
      CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        username TEXT NOT NULL,
        expires_at DATETIME NOT NULL
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
        is_active INTEGER DEFAULT 1,
        ntfy_url TEXT,
        ntfy_template TEXT,
        is_api INTEGER DEFAULT 0,
        request_headers TEXT
      );
    `);
    
    // Migracje dla istniejących baz
    try { db.exec('ALTER TABLE scraping_sources ADD COLUMN ntfy_url TEXT'); } catch(e) {}
    try { db.exec('ALTER TABLE scraping_sources ADD COLUMN ntfy_template TEXT'); } catch(e) {}
    try { db.exec('ALTER TABLE scraping_sources ADD COLUMN is_api INTEGER DEFAULT 0'); } catch(e) {}
    try { db.exec('ALTER TABLE scraping_sources ADD COLUMN request_headers TEXT'); } catch(e) {}

  } catch (error) {
    console.error("Błąd połączenia z bazą danych:", error);
    db = null; // Upewniamy się, że db jest null w razie błędu
  }
} else {
  console.log("Jesteśmy w trakcie budowania (build), pomijam połączenie z bazą danych.");
}

export default db;