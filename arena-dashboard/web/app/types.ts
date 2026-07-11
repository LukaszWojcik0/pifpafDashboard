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

export interface Snapshot {
  id: number;
  event_id: string;
  available: number | null;
  status: string;
  checked_at: string;
}
