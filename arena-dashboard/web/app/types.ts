export interface Event {
  id: number;
  url: string;
  title: string;
  event_date: string;
  event_time: string;
  max_available: number;
  first_seen: string;
  last_seen: string;
  status: string;
}

export interface Snapshot {
  id: number;
  event_id: number;
  available: number;
  checked_at: string;
}