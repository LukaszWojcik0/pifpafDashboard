export interface Event {
  id: string;
  title: string;
  link: string;
  event_date: string;
  event_time: string;
  status: string;
  max_available: number | null;
  last_seen: string;
}

export interface Snapshot {
  id: number;
  event_id: string;
  available: number;
  checked_at: string;
}