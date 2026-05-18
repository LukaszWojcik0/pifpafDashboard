export interface Event {
  id: string;
  title: string;
  link: string | null;
  date_info: string | null;
  max_available: number;
  last_seen: string | null;
  created_at: string;
  current_available?: number; // Fetched from latest snapshot
}

export interface EventSnapshot {
  id: number;
  event_id: string;
  available_places: number;
  timestamp: string;
}
