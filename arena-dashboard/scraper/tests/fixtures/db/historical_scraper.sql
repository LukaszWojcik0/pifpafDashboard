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
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(event_id) REFERENCES events(id)
);

CREATE TABLE system_status (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE scraping_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    list_url TEXT NOT NULL,
    list_links_selector TEXT,
    title_selector TEXT,
    date_selector TEXT,
    time_selector TEXT,
    image_selector TEXT,
    tickets_regex TEXT,
    sold_out_regex TEXT,
    is_active INTEGER DEFAULT 1,
    is_api INTEGER DEFAULT 0,
    request_headers TEXT,
    ntfy_url TEXT,
    ntfy_template TEXT
);

INSERT INTO scraping_sources (id, name, list_url, list_links_selector, title_selector, is_active)
VALUES (1, 'Arena Walki', 'https://arenawalki.pl/gry-otwarte/', 'a[href*="/events/"]', 'h1', 1);

INSERT INTO events (id, title, link, date_info, max_available, last_seen, created_at, image_url)
VALUES ('legacy-1', 'Legacy Alpha', 'https://arenawalki.pl/events/alpha', '2026-01-01 18:00', 12, '2026-01-01 10:00:00', '2026-01-01 09:00:00', NULL);

INSERT INTO event_snapshots (event_id, available_places, timestamp)
VALUES ('legacy-1', 10, '2026-01-01 10:00:00');
