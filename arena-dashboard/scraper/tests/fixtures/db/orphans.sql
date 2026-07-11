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

INSERT INTO events (id, title, link, date_info, max_available, last_seen)
VALUES ('kept', 'Kept', 'https://arenawalki.pl/events/kept', '2026-04-01', 4, '2026-04-01T10:00:00Z');

INSERT INTO event_snapshots (event_id, available_places, timestamp)
VALUES
    ('kept', 4, '2026-04-01T10:00:00Z'),
    ('missing-event', 7, '2026-04-01T10:05:00Z');
