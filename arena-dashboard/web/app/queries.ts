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
        id, title, link, date_info as event_date, '' as event_time, 
        CASE WHEN max_available <= 0 THEN 'wyprzedane' ELSE 'aktywne' END as status, 
        max_available, last_seen 
      FROM events 
      ORDER BY last_seen DESC
    `);
    return stmt.all() as Event[];
  } catch (error) {
    console.error("Błąd podczas pobierania wydarzeń:", error);
    return [];
  }
}

/**
 * Pobiera pojedyncze wydarzenie po jego ID.
 * Zwraca null, jeśli baza nie jest dostępna lub wydarzenie nie zostało znalezione.
 */
export function getEventById(id: string): Event | null {
  if (!db) return null;
  try {
    const stmt = db.prepare(\`
      SELECT 
        id, title, link, date_info as event_date, '' as event_time, 
        CASE WHEN max_available <= 0 THEN 'wyprzedane' ELSE 'aktywne' END as status, 
        max_available, last_seen 
      FROM events 
      WHERE id = ?
    \`);
    return (stmt.get(id) as Event) || null;
  } catch (error) {
    console.error(\`Błąd podczas pobierania wydarzenia \${id}:\`, error);
    return null;
  }
}

/**
 * Pobiera historię dostępności (snapshots) dla danego wydarzenia.
 */
export function getEventSnapshots(eventId: string): Snapshot[] {
  if (!db) return [];
  try {
    const stmt = db.prepare(\`
      SELECT id, event_id, available_places as available, timestamp as checked_at 
      FROM event_snapshots 
      WHERE event_id = ? 
      ORDER BY timestamp ASC
    \`);
    return stmt.all(eventId) as Snapshot[];
  } catch (error) {
    console.error(\`Błąd podczas pobierania snapshotów dla wydarzenia \${eventId}:\`, error);
    return [];
  }
}