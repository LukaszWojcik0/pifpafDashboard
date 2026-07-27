import db from './db';
import { AdminEvent, Event, ScraperStatus, Snapshot } from './types';
import { classifyEvent, eventVisibilityReason } from './eventVisibility.mjs';
import { calculateCumulativePlayers } from './playerCounts.mjs';

export function getEvents(): Event[] {
  if (!db) return [];
  const stmt = db.prepare(`
    SELECT
      events.id,
      events.title,
      events.url AS link,
      events.event_date,
      events.event_time,
      events.status,
      events.max_available,
      events.current_available,
      events.image_url,
      events.last_seen,
      scraping_sources.name AS source_name,
      NULL AS potential_players
    FROM events
    LEFT JOIN scraping_sources ON scraping_sources.id = events.source_id
    ORDER BY events.last_seen DESC
  `);
  return withPotentialPlayers(stmt.all() as Event[]);
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
      events.id,
      events.title,
      events.url AS link,
      events.event_date,
      events.event_time,
      events.status,
      events.max_available,
      events.current_available,
      events.image_url,
      events.last_seen,
      scraping_sources.name AS source_name,
      NULL AS potential_players
    FROM events
    LEFT JOIN scraping_sources ON scraping_sources.id = events.source_id
    WHERE events.id = ?
  `);
  const event = (stmt.get(id) as Event) || null;
  return event ? withPotentialPlayers([event])[0] : null;
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

function calculatePotentialPlayers(event: Event): number | null {
  if (!db || event.max_available === null || event.max_available === undefined) return null;
  const rows = db.prepare(`
    SELECT available
    FROM snapshots
    WHERE event_id = ? AND available IS NOT NULL
    ORDER BY checked_at ASC, id ASC
  `).all(event.id) as { available: number }[];
  return calculateCumulativePlayers(
    event.max_available,
    rows.map((row) => row.available),
    event.current_available,
  );
}

function withPotentialPlayers(events: Event[]): Event[] {
  return events.map((event) => ({
    ...event,
    potential_players: calculatePotentialPlayers(event),
  }));
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
