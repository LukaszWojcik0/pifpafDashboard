import { getDb } from './db';
import { Event, EventSnapshot } from './types';

export function getEvents(): Event[] {
  const db = getDb();
  const events = db.prepare(`
    SELECT e.*, 
      (SELECT available_places FROM event_snapshots es WHERE es.event_id = e.id ORDER BY timestamp DESC LIMIT 1) as current_available
    FROM events e
    ORDER BY e.created_at DESC
  `).all() as Event[];
  return events;
}

export function getEventById(id: string): Event | undefined {
  const db = getDb();
  const event = db.prepare(`
    SELECT e.*, 
      (SELECT available_places FROM event_snapshots es WHERE es.event_id = e.id ORDER BY timestamp DESC LIMIT 1) as current_available
    FROM events e
    WHERE e.id = ?
  `).get(id) as Event | undefined;
  return event;
}

export function getEventSnapshots(id: string): EventSnapshot[] {
  const db = getDb();
  return db.prepare(`
    SELECT * FROM event_snapshots
    WHERE event_id = ?
    ORDER BY timestamp ASC
  `).all(id) as EventSnapshot[];
}
