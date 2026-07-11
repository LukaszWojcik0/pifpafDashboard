import logging
import os
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = os.getenv('DATABASE_PATH', 'app.db')


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else '.', exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            link TEXT,
            date_info TEXT,
            max_available INTEGER DEFAULT 0,
            last_seen TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            image_url TEXT
        )
    ''')

    try:
        cursor.execute('ALTER TABLE events ADD COLUMN image_url TEXT')
    except sqlite3.OperationalError:
        pass

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL,
            available_places INTEGER NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(event_id) REFERENCES events(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_status (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scraping_sources (
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
            request_headers TEXT
        )
    ''')

    for column_sql in [
        'ALTER TABLE scraping_sources ADD COLUMN ntfy_url TEXT',
        'ALTER TABLE scraping_sources ADD COLUMN ntfy_template TEXT',
        'ALTER TABLE scraping_sources ADD COLUMN is_api INTEGER DEFAULT 0',
        'ALTER TABLE scraping_sources ADD COLUMN request_headers TEXT',
    ]:
        try:
            cursor.execute(column_sql)
        except sqlite3.OperationalError:
            pass

    cursor.execute('SELECT count(*) FROM scraping_sources')
    if cursor.fetchone()[0] == 0:
        logger.info('No scraping sources found. Initializing default Arena Walki source.')
        cursor.execute('''
            INSERT INTO scraping_sources
            (name, list_url, list_links_selector, title_selector, date_selector, time_selector, image_selector, tickets_regex, sold_out_regex)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            'Arena Walki',
            'https://arenawalki.pl/gry-otwarte/',
            'a[href*="/produkt/"], a[href*="/wydarzenie/"], a[href*="/events/"]',
            'h1',
            '[class*="date"], [class*="data"]',
            '[class*="time"], [class*="czas"], [class*="godzina"]',
            'meta[property="og:image"], .wp-post-image, .woocommerce-product-gallery__image img',
            r'\((\d+)\s+dost(?:epnych|ępnych|Ä™pnych)\)',
            r'wyprzedane|brak biletow|brak biletów|brak w magazynie|sprzedaz zamknieta|sprzedaż zamknięta',
        ))

    conn.commit()
    conn.close()
    logger.info('Database initialized at %s', DB_PATH)


def update_status(key, value):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO system_status (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    ''', (key, value))
    conn.commit()
    conn.close()


def update_event(event_id, title, link, date_info, available_places, image_url=None):
    """Insert or update an event without treating unknown availability as zero.

    available_places=None means that the current scrape could not produce a
    trustworthy measurement. In that case event metadata is refreshed, the last
    known max_available is preserved, and no snapshot is written.
    """
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now()

    cursor.execute('SELECT max_available FROM events WHERE id = ?', (event_id,))
    row = cursor.fetchone()

    measurement_known = available_places is not None
    max_available = available_places if measurement_known else None
    is_new = row is None

    if is_new:
        cursor.execute('''
            INSERT INTO events (id, title, link, date_info, max_available, last_seen, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (event_id, title, link, date_info, max_available, now, image_url))
    else:
        current_max = row[0]
        if measurement_known:
            max_available = max(current_max or 0, available_places)
        else:
            max_available = current_max
        cursor.execute('''
            UPDATE events
            SET title = ?, link = ?, date_info = ?, max_available = ?, last_seen = ?, image_url = ?
            WHERE id = ?
        ''', (title, link, date_info, max_available, now, image_url, event_id))

    if measurement_known:
        cursor.execute('''
            INSERT INTO event_snapshots (event_id, available_places, timestamp)
            VALUES (?, ?, ?)
        ''', (event_id, available_places, now))

    conn.commit()
    conn.close()

    return is_new, max_available, measurement_known
