import sqlite3
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = os.getenv('DATABASE_PATH', 'app.db')

def get_connection():
    # Ensure directory exists if it's a specific path
    os.makedirs(os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else '.', exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Create events table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            link TEXT,
            date_info TEXT,
            max_available INTEGER DEFAULT 0,
            last_seen TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create snapshots table for historical tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL,
            available_places INTEGER NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(event_id) REFERENCES events(id)
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {DB_PATH}")

def update_event(event_id, title, link, date_info, available_places):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now()
    
    cursor.execute('SELECT max_available FROM events WHERE id = ?', (event_id,))
    row = cursor.fetchone()
    
    max_available = available_places
    is_new = row is None
    
    if is_new:
        cursor.execute('''
            INSERT INTO events (id, title, link, date_info, max_available, last_seen)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (event_id, title, link, date_info, max_available, now))
    else:
        current_max = row[0]
        max_available = max(current_max, available_places)
        cursor.execute('''
            UPDATE events 
            SET title = ?, link = ?, date_info = ?, max_available = ?, last_seen = ?
            WHERE id = ?
        ''', (title, link, date_info, max_available, now, event_id))
    
    # Record snapshot
    cursor.execute('''
        INSERT INTO event_snapshots (event_id, available_places, timestamp)
        VALUES (?, ?, ?)
    ''', (event_id, available_places, now))
    
    conn.commit()
    conn.close()
    
    return is_new, max_available
