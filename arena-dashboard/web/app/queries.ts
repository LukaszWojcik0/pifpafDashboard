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
        e.status, e.max_available, e.last_seen,
        (SELECT available FROM snapshots WHERE event_id = e.id ORDER BY checked_at DESC LIMIT 1) as current_available
      FROM events e
      ORDER BY e.last_seen DESC
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
    const stmt = db.prepare(`
      SELECT 
        id, title, url as link, event_date, event_time, 
        status, max_available, last_seen 
      FROM events 
      WHERE id = ?
    `);
    return (stmt.get(id) as Event) || null;
  } catch (error) {
    console.error(`Błąd podczas pobierania wydarzenia ${id}:`, error);
    return null;
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
    console.error(
      `Błąd podczas pobierania snapshotów dla wydarzenia ${eventId}:`,
      error,
    );
    return [];
  }
}