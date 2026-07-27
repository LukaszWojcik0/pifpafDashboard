export interface Event {
  id: string;
  title: string;
  link: string;
  event_date: string;
  event_time: string;
  status: string;
  max_available: number | null;
  current_available: number | null;
  image_url: string | null;
  last_seen: string;
}

export interface AdminEvent extends Event {
  visibility: 'public' | 'needs_review' | 'past';
  visibility_reason: string;
}

export interface Snapshot {
  id: number;
  event_id: string;
  available: number | null;
  status: string;
  checked_at: string;
}

export interface ScraperStatus {
  status: string | null;
  lastStartedAt: string | null;
  lastFinishedAt: string | null;
  lastSuccessAt: string | null;
  lastErrorAt: string | null;
  lastErrorReason: string | null;
  durationSeconds: number | null;
  summary: {
    sources?: number;
    found?: number;
    valid?: number;
    rejected?: number;
    created?: number;
    updated?: number;
    skipped?: boolean;
  };
  stale: boolean;
  staleAfterMinutes: number;
}
