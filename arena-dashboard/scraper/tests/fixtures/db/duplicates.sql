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
VALUES
    ('dup-a', 'Duplicate A', 'https://arenawalki.pl/events/duplicate', '2026-03-01', 10, '2026-03-01T10:00:00Z'),
    ('dup-b', 'Duplicate B', 'https://arenawalki.pl/events/duplicate', '2026-03-01', 9, '2026-03-01T10:05:00Z');

INSERT INTO event_snapshots (event_id, available_places, timestamp)
VALUES
    ('dup-a', 10, '2026-03-01T10:00:00Z'),
    ('dup-b', 9, '2026-03-01T10:05:00Z');
