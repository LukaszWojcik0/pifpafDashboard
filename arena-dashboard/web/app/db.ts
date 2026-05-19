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
  } catch (error) {
    console.error("Błąd połączenia z bazą danych:", error);
    db = null; // Upewniamy się, że db jest null w razie błędu
  }
} else {
  console.log("Jesteśmy w trakcie budowania (build), pomijam połączenie z bazą danych.");
}

export default db;