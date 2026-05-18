import db from './db';
import { Event, Snapshot } from './types';

export function getEvents(): Event[] {
  try {
    // Używamy dat jako sortowania (od najświeższych)
    return db.prepare('SELECT * FROM events ORDER BY event_date DESC, event_time DESC').all() as Event[];
  } catch (e) {
    console.error('Błąd bazy danych getEvents:', e);
    return [];
  }
}

export function getEventById(id: number): Event | undefined {
  try {
    return db.prepare('SELECT * FROM events WHERE id = ?').get(id) as Event | undefined;
  } catch (e) {
    console.error('Błąd bazy danych getEventById:', e);
    return undefined;
  }
}

export function getEventSnapshots(eventId: number): Snapshot[] {
  try {
    return db.prepare('SELECT * FROM snapshots WHERE event_id = ? ORDER BY checked_at ASC').all(eventId) as Snapshot[];
  } catch (e) {
    console.error('Błąd bazy danych getEventSnapshots:', e);
    return [];
  }
}