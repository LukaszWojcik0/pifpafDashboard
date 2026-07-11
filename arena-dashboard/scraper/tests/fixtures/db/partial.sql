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

CREATE TABLE scraping_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    list_url TEXT NOT NULL,
    is_active INTEGER DEFAULT 1
);

INSERT INTO users (username, password_hash, salt)
VALUES ('admin', 'hash', 'salt');

INSERT INTO sessions (token, username, expires_at)
VALUES ('token', 'admin', '2027-01-01T00:00:00Z');

INSERT INTO scraping_sources (name, list_url, is_active)
VALUES ('Only source', 'https://example.test/events', 1);
