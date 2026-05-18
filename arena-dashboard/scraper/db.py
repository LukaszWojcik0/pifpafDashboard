import sqlite3
import os
import logging
from datetime import datetime
from typing import Dict, Optional, Tuple

from alerts import send_ntfy_alert

logger = logging.getLogger(__name__)

def get_db_path() -> str:
    return os.environ.get("DATABASE_PATH", "/data/app.db")

def init_db():
    db_path = get_db_path()
    # Create directory if it doesn't exist (useful for local runs)
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else '.', exist_ok=True)
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        # Using WAL mode for better concurrency since Next.js will read simultaneously
        cursor.execute("PRAGMA journal_mode=WAL;")
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT,
                event_date TEXT,
                event_time TEXT,
                max_available INTEGER,
                first_seen TEXT,
                last_seen TEXT,
                status TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                available INTEGER,
                checked_at TEXT NOT NULL,
                FOREIGN KEY (event_id) REFERENCES events (id)
            )
        ''')
        conn.commit()

def upsert_event(conn: sqlite3.Connection, event: Dict, is_first_run: bool = False) -> int:
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    url = event.get("url")
    title = event.get("title")
    event_date = event.get("date")
    event_time = event.get("time")
    available = event.get("tickets_available")
    status = event.get("status")

    cursor.execute("SELECT id, max_available, status FROM events WHERE url = ?", (url,))
    row = cursor.fetchone()

    event_id = None
    previous_available = None
    previous_status = None
    is_new = False

    if row is None:
        is_new = True
        max_available = available if available is not None else 0
        cursor.execute('''
            INSERT INTO events (url, title, event_date, event_time, max_available, first_seen, last_seen, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (url, title, event_date, event_time, max_available, now, now, status))
        event_id = cursor.lastrowid
    else:
        event_id, current_max_available, previous_status = row
        max_available = current_max_available
        if available is not None and (current_max_available is None or available > current_max_available):
            max_available = available
        
        cursor.execute('''
            UPDATE events
            SET title = ?, event_date = ?, event_time = ?, status = ?, last_seen = ?, max_available = ?
            WHERE id = ?
        ''', (title, event_date, event_time, status, now, max_available, event_id))
        
        cursor.execute("SELECT available FROM snapshots WHERE event_id = ? ORDER BY id DESC LIMIT 1", (event_id,))
        snap_row = cursor.fetchone()
        if snap_row:
            previous_available = snap_row[0]
    
    conn.commit()
    
    _check_and_send_alerts(
        is_first_run=is_first_run,
        is_new=is_new,
        title=title,
        event_date=event_date,
        event_time=event_time,
        url=url,
        status=status,
        previous_status=previous_status,
        available=available,
        previous_available=previous_available
    )
    
    return event_id

def save_snapshot(conn: sqlite3.Connection, event_id: int, available: Optional[int]):
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute('''
        INSERT INTO snapshots (event_id, available, checked_at)
        VALUES (?, ?, ?)
    ''', (event_id, available, now))
    conn.commit()

def _check_and_send_alerts(is_first_run: bool, is_new: bool, title: Optional[str], event_date: Optional[str], event_time: Optional[str], url: str, status: str, previous_status: Optional[str], available: Optional[int], previous_available: Optional[int]):
    ntfy_url = os.environ.get("NTFY_URL")
    alert_on_first_run = os.environ.get("ALERT_ON_FIRST_RUN", "false").lower() == "true"

    if ntfy_url and not (is_first_run and not alert_on_first_run):
        alert_title = None
        
        if is_new:
            alert_title = "Nowe wydarzenie!"
        else:
            if previous_status != status:
                if status == "Wyprzedane":
                    alert_title = "Wydarzenie wyprzedane!"
                elif status == "Sprzedaż zamknięta":
                    alert_title = "Sprzedaż zamknięta!"
                    
            if not alert_title and previous_available != available:
                if previous_available is not None and available is not None:
                    if available < previous_available:
                        alert_title = "Liczba biletów spadła"
                    elif available > previous_available:
                        alert_title = "Liczba biletów wzrosła"
                elif previous_available is None and available is not None:
                    alert_title = "Liczba biletów wzrosła"
                elif previous_available is not None and available is None:
                    alert_title = "Liczba biletów spadła"

        if alert_title:
            safe_title = title if title else "Brak tytułu"
            safe_date = event_date if event_date else ""
            safe_time = event_time if event_time else ""
            send_ntfy_alert(ntfy_url, alert_title, safe_title, safe_date, safe_time, previous_available, available, url)
