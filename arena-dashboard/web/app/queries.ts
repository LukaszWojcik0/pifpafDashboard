import db from './db';
import { AdminEvent, Event, ScraperStatus, Snapshot } from './types';
import { classifyEvent, eventVisibilityReason } from './eventVisibility.mjs';

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

export function getPublicEvents(): Event[] {
  return getEvents().filter((event) => classifyEvent(event) === 'public');
}

export function getAdminEvents(): AdminEvent[] {
  return getEvents().map((event) => {
    const visibility = classifyEvent(event);
    return {
      ...event,
      visibility,
      visibility_reason: eventVisibilityReason(event),
    };
  });
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

function parseSummary(value: string | null): ScraperStatus['summary'] {
  if (!value) return {};
  try {
    const parsed = JSON.parse(value) as ScraperStatus['summary'];
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

function numberOrNull(value: string | null): number | null {
  if (!value) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function staleAfterMinutes(): number {
  const configured = Number(process.env.STALE_AFTER_MINUTES ?? '30');
  return Number.isFinite(configured) && configured > 0 ? configured : 30;
}

export function getScraperStatus(): ScraperStatus {
  const threshold = staleAfterMinutes();
  if (!db) {
    return {
      status: 'unavailable',
      lastStartedAt: null,
      lastFinishedAt: null,
      lastSuccessAt: null,
      lastErrorAt: null,
      lastErrorReason: 'database_unavailable',
      durationSeconds: null,
      summary: {},
      stale: true,
      staleAfterMinutes: threshold,
    };
  }

  const rows = db.prepare('SELECT key, value FROM system_status').all() as { key: string; value: string }[];
  const statusMap = new Map(rows.map((row) => [row.key, row.value]));
  const lastSuccessAt = statusMap.get('last_success_at') ?? null;
  const lastSuccessMs = lastSuccessAt ? new Date(lastSuccessAt).getTime() : Number.NaN;
  const stale = !Number.isFinite(lastSuccessMs) || Date.now() - lastSuccessMs > threshold * 60 * 1000;

  return {
    status: statusMap.get('last_scrape_status') ?? null,
    lastStartedAt: statusMap.get('last_scrape_started_at') ?? null,
    lastFinishedAt: statusMap.get('last_scrape_finished_at') ?? null,
    lastSuccessAt,
    lastErrorAt: statusMap.get('last_error_at') ?? null,
    lastErrorReason: statusMap.get('last_error_reason') ?? null,
    durationSeconds: numberOrNull(statusMap.get('last_scrape_duration_seconds') ?? null),
    summary: parseSummary(statusMap.get('last_scrape_summary') ?? null),
    stale,
    staleAfterMinutes: threshold,
  };
}
