CREATE TABLE events (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    link TEXT,
    date_info TEXT,
    max_available INTEGER DEFAULT 0,
    last_seen TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    image_url TEXT
);

CREATE TABLE event_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    available_places INTEGER NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO events (id, title, link, date_info, max_available, last_seen, created_at)
VALUES ('time-1', 'Time Alpha', 'https://arenawalki.pl/events/time-alpha', '2025-12-31 23:00', 5, '2025-12-31 22:00:00', '2025-12-31 21:00:00');

INSERT INTO event_snapshots (event_id, available_places, timestamp)
VALUES ('time-1', 5, '2025-12-31 22:00:00');
