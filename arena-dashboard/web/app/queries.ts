import db from './db';
import { Event, Snapshot } from './types';

/**
 * Pobiera wszystkie wydarzenia z bazy danych.
 * Zwraca pustą tablicę, jeśli baza danych nie jest dostępna (np. podczas budowania).
 */
export function getEvents(): Event[] {
  if (!db) return [];
  try {
    const stmt = db.prepare(`
      SELECT 
        e.id, e.title, e.url as link, e.event_date, e.event_time, 
        e.status, e.max_available, e.last_seen, e.image_url,
        (SELECT available FROM snapshots WHERE event_id = e.id ORDER BY checked_at DESC LIMIT 1) as current_available
      FROM events e
      ORDER BY e.last_seen DESC
    `);

    const results = stmt.all() as Event[];
    console.log(
      `[DB DEBUG] Pobrano ${results.length} wydarzeń z głównego zapytania.`,
    );
    if (results.length > 0) {
      console.log("[DB DEBUG] Przykładowy event (nowy schemat):", results[0]);
    }
    return results;
  } catch (error) {
    console.error(
      "[DB DEBUG] Błąd głównego zapytania (przechodzę na zapasowe):",
      error.message,
    );
    try {
      // Zapasowe zapytanie dla starszych plików bazy danych
      const fallbackStmt = db.prepare(`
        SELECT 
          id, title, link, date_info as event_date, '' as event_time, 
          CASE WHEN max_available <= 0 THEN 'Wyprzedane' ELSE 'Bilety dostępne' END as status, 
          max_available, last_seen, image_url,
          (SELECT available_places FROM event_snapshots WHERE event_id = events.id ORDER BY timestamp DESC LIMIT 1) as current_available
        FROM events 
        ORDER BY last_seen DESC
      `);

      const fallbackResults = fallbackStmt.all() as Event[];
      console.log(
        `[DB DEBUG] Pobrano ${fallbackResults.length} wydarzeń z ZAPASOWEGO zapytania.`,
      );
      if (fallbackResults.length > 0) {
        console.log(
          "[DB DEBUG] Przykładowy event (stary schemat):",
          fallbackResults[0],
        );
      }
      return fallbackResults;
    } catch (fallbackError) {
      console.error(
        "Błąd podczas pobierania wydarzeń (oba schematy zawiodły):",
        fallbackError,
      );
      return [];
    }
  }
}

/**
 * Pobiera pojedyncze wydarzenie po jego ID.
 * Zwraca null, jeśli baza nie jest dostępna lub wydarzenie nie zostało znalezione.
 */
export function getEventById(id: string): Event | null {
  if (!db) return null;
  try {
    const stmt = db.prepare(`
      SELECT 
        id, title, url as link, event_date, event_time, 
        status, max_available, last_seen, image_url
      FROM events 
      WHERE id = ?
    `);
    return (stmt.get(id) as Event) || null;
  } catch (error) {
    try {
      // Zapasowe zapytanie dla starszych plików bazy danych
      const fallbackStmt = db.prepare(`
        SELECT 
          id, title, link, date_info as event_date, '' as event_time, 
          CASE WHEN max_available <= 0 THEN 'Wyprzedane' ELSE 'Bilety dostępne' END as status, 
          max_available, last_seen, image_url
        FROM events 
        WHERE id = ?
      `);
      return (fallbackStmt.get(id) as Event) || null;
    } catch (fallbackError) {
      console.error(`Błąd podczas pobierania wydarzenia ${id}:`, fallbackError);
      return null;
    }
  }
}

/**
 * Pobiera historię dostępności (snapshots) dla danego wydarzenia.
 */
export function getEventSnapshots(eventId: string): Snapshot[] {
  if (!db) return [];
  try {
    const stmt = db.prepare(`
      SELECT id, event_id, available, checked_at 
      FROM snapshots 
      WHERE event_id = ? 
      ORDER BY checked_at ASC
    `);
    return stmt.all(eventId) as Snapshot[];
  } catch (error) {
    try {
      // Zapasowe zapytanie dla starszych plików bazy danych
      const fallbackStmt = db.prepare(`
        SELECT id, event_id, available_places as available, timestamp as checked_at 
        FROM event_snapshots 
        WHERE event_id = ? 
        ORDER BY timestamp ASC
      `);
      return fallbackStmt.all(eventId) as Snapshot[];
    } catch (fallbackError) {
      console.error(`Błąd pobierania snapshotów ${eventId}:`, fallbackError);
      return [];
    }
  }
}