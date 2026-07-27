const UNKNOWN_TITLES = new Set([
  '',
  'brak tytulu',
  'brak tytułu',
  'nieznane wydarzenie',
  'nieznane wydarzenie api',
  'untitled event',
]);

export function todayIsoDate(now = new Date()) {
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function normalizeEventDate(value) {
  const text = String(value || '').trim();
  const match = text.match(/^(\d{4}-\d{2}-\d{2})/);
  return match ? match[1] : null;
}

export function isPastEvent(event, now = new Date()) {
  const eventDate = normalizeEventDate(event?.event_date);
  if (!eventDate) return false;
  return eventDate < todayIsoDate(now);
}

export function isUncertainEvent(event) {
  const title = String(event?.title || '').trim().toLowerCase();
  if (UNKNOWN_TITLES.has(title)) return true;
  if (!normalizeEventDate(event?.event_date)) return true;
  if (String(event?.status || '').toLowerCase() === 'unknown') return true;
  if (event?.current_available === null || event?.current_available === undefined) return true;
  return false;
}

export function classifyEvent(event, now = new Date()) {
  if (isPastEvent(event, now)) return 'past';
  if (isUncertainEvent(event)) return 'needs_review';
  return 'public';
}

export function eventVisibilityLabel(classification) {
  if (classification === 'past') return 'Archiwalne';
  if (classification === 'needs_review') return 'Do sprawdzenia';
  return 'Publiczne';
}

export function eventVisibilityReason(event, now = new Date()) {
  if (isPastEvent(event, now)) return 'Data wydarzenia jest starsza niz dzisiaj.';
  const title = String(event?.title || '').trim().toLowerCase();
  if (UNKNOWN_TITLES.has(title)) return 'Brak pewnego tytulu.';
  if (!normalizeEventDate(event?.event_date)) return 'Brak pewnej daty.';
  if (String(event?.status || '').toLowerCase() === 'unknown') return 'Status dostepnosci jest nieznany.';
  if (event?.current_available === null || event?.current_available === undefined) return 'Brak pewnego pomiaru miejsc.';
  return 'Widoczne publicznie.';
}
