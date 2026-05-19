import Database, { Database as DB } from 'better-sqlite3';
import path from 'path';
import fs from 'fs';

// W kontenerze używamy zmiennej env. Na lokalnych środowiskach fallback do katalogu z aplikacją
const dbPath = process.env.DATABASE_PATH || path.join(process.cwd(), '../data/app.db');

let db: DB | null = null;

// Ta funkcja zapobiega próbie połączenia z plikiem bazy danych podczas procesu budowania (npm run build),
// kiedy plik fizycznie nie istnieje w kontenerze budującym.
if (process.env.npm_lifecycle_event !== 'build') {
  try {
    db = new Database(dbPath, { readonly: true });
    // Nie używamy pragmy na bazie tylko do odczytu
    // db.pragma('journal_mode = WAL');
  } catch (error) {
    console.error("Błąd połączenia z bazą danych:", error);
    db = null; // Upewniamy się, że db jest null w razie błędu
  }
} else {
  console.log("Jesteśmy w trakcie budowania (build), pomijam połączenie z bazą danych.");
}

export default db;