CREATE TABLE events (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    event_date TEXT,
    event_time TEXT,
    status TEXT,
    max_available INTEGER,
    last_seen TEXT,
    image_url TEXT
);

CREATE TABLE snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    available INTEGER NOT NULL,
    checked_at TEXT NOT NULL
);

CREATE TABLE users (
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL
);

CREATE TABLE sessions (
    token TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    expires_at DATETIME NOT NULL
);

INSERT INTO users (username, password_hash, salt)
VALUES ('admin', 'hash', 'salt');

INSERT INTO sessions (token, username, expires_at)
VALUES ('token', 'admin', '2027-01-01T00:00:00Z');

INSERT INTO events (id, title, url, event_date, event_time, status, max_available, last_seen, image_url)
VALUES ('web-1', 'Web Alpha', 'https://arenawalki.pl/events/web-alpha', '2026-02-01', '19:00', 'Bilety dostepne', 20, '2026-02-01T10:00:00Z', NULL);

INSERT INTO snapshots (event_id, available, checked_at)
VALUES ('web-1', 18, '2026-02-01T10:00:00Z');
