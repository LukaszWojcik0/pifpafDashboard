import db from './db';
import { Event, Snapshot } from './types';

export function getEvents(): Event[] {
  if (!db) return [];
  const stmt = db.prepare(`
    SELECT
      id,
      title,
      url AS link,
      event_date,
      event_time,
      status,
      max_available,
      current_available,
      image_url,
      last_seen
    FROM events
    ORDER BY last_seen DESC
  `);
  return stmt.all() as Event[];
}

export function getEventById(id: string): Event | null {
  if (!db) return null;
  const stmt = db.prepare(`
    SELECT
      id,
      title,
      url AS link,
      event_date,
      event_time,
      status,
      max_available,
      current_available,
      image_url,
      last_seen
    FROM events
    WHERE id = ?
  `);
  return (stmt.get(id) as Event) || null;
}

export function getEventSnapshots(eventId: string, limit = 1000): Snapshot[] {
  if (!db) return [];
  const safeLimit = Math.min(Math.max(Math.trunc(limit), 1), 5000);
  const stmt = db.prepare(`
    SELECT id, event_id, available, status, checked_at
    FROM snapshots
    WHERE event_id = ?
    ORDER BY checked_at DESC, id DESC
    LIMIT ?
  `);
  return (stmt.all(eventId, safeLimit) as Snapshot[]).reverse();
}
