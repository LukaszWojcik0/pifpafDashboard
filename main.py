import json
import logging
import os
import re
import sqlite3
import traceback
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from apscheduler.schedulers.blocking import BlockingScheduler

# Ustawienie prostego logowania, aby kontrolować przebieg działania, 
# nie psując samego formatu wyjściowego (logi pójdą na stderr/stdout z prefixem)
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

BASE_URL = "https://arenawalki.pl/gry-otwarte/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}
DB_FILE = os.environ.get("DATABASE_PATH", "events.db")

def init_db(db_path: str = DB_FILE):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
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

def send_ntfy(ntfy_url: str, title: str, event_title: str, event_date: str, event_time: str, prev_avail: Optional[int], curr_avail: Optional[int], url: str):
    prev_str = str(prev_avail) if prev_avail is not None else 'Brak'
    curr_str = str(curr_avail) if curr_avail is not None else 'Brak'
    
    message = (
        f"Nazwa: {event_title}\n"
        f"Data: {event_date} {event_time}\n"
        f"Poprzednio: {prev_str}\n"
        f"Aktualnie: {curr_str}"
    )
    
    headers = {
        "Title": title.encode('utf-8'),
        "Click": url
    }
    
    try:
        requests.post(ntfy_url, data=message.encode('utf-8'), headers=headers, timeout=5)
    except Exception as e:
        logging.error(f"Błąd wysyłania powiadomienia ntfy: {e}")

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
            send_ntfy(ntfy_url, alert_title, safe_title, safe_date, safe_time, previous_available, available, url)

    return event_id

def save_snapshot(conn: sqlite3.Connection, event_id: int, available: Optional[int]):
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute('''
        INSERT INTO snapshots (event_id, available, checked_at)
        VALUES (?, ?, ?)
    ''', (event_id, available, now))
    conn.commit()

def get_event_urls(session: requests.Session, list_url: str) -> List[str]:
    """
    Pobiera listę adresów URL poszczególnych wydarzeń ze strony głównej.
    """
    try:
        response = session.get(list_url, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Błąd HTTP podczas pobierania listy wydarzeń z {list_url}: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    event_urls = set()

    for link in soup.find_all('a', href=True):
        href = link['href']
        text = link.get_text(separator=' ', strip=True).lower()
        
        if "dołącz" in text or "kup" in text or "bilet" in text or "/produkt/" in href or "/wydarzenie/" in href:
            full_url = urljoin(list_url, href)
            if full_url != list_url:
                event_urls.add(full_url)

    return list(event_urls)


def scrape_event_details(session: requests.Session, event_url: str) -> Optional[Dict]:
    """
    Wchodzi pod adres URL wydarzenia i wyciąga niezbędne informacje.
    """
    try:
        response = session.get(event_url, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Błąd HTTP podczas pobierania szczegółów z {event_url}: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')
    
    data = {
        "title": None,
        "url": event_url,
        "date": None,
        "time": None,
        "tickets_available": None,
        "status": "Nieznany"
    }

    title_element = soup.find('h1')
    if title_element:
        data["title"] = title_element.get_text(strip=True)

    date_element = soup.find(class_=re.compile(r'date|data', re.I))
    if date_element:
        data["date"] = date_element.get_text(strip=True)

    time_element = soup.find(class_=re.compile(r'time|czas|godzina', re.I))
    if time_element:
        data["time"] = time_element.get_text(strip=True)

    page_text = soup.get_text(separator=' ', strip=True)
    tickets_match = re.search(r'\((\d+)\s+dostępnych\)', page_text, re.IGNORECASE)
    
    if tickets_match:
        data["tickets_available"] = int(tickets_match.group(1))
        data["status"] = "Bilety dostępne"
    else:
        page_text_lower = page_text.lower()
        if "sprzedaż zamknięta" in page_text_lower:
            data["tickets_available"] = 0
            data["status"] = "Sprzedaż zamknięta"
        elif "wyprzedane" in page_text_lower or "brak biletów" in page_text_lower or "brak w magazynie" in page_text_lower:
            data["tickets_available"] = 0
            data["status"] = "Wyprzedane"
        else:
            data["tickets_available"] = None
            data["status"] = "Brak informacji"

    return data


def scrape_arena_events() -> List[Dict]:
    """
    Główna funkcja orkiestrująca scraper. Łączy pozyskiwanie URL-i oraz wyciąganie detali.
    """
    with requests.Session() as session:
        session.headers.update(HEADERS)
        
        logging.info(f"Rozpoczynam pobieranie linków do wydarzeń z: {BASE_URL}")
        event_urls = get_event_urls(session, BASE_URL)
        
        if not event_urls:
            logging.warning("Nie znaleziono żadnych wydarzeń. Sprawdź selektory w funkcji get_event_urls().")
            return []
            
        logging.info(f"Znaleziono {len(event_urls)} potencjalnych wydarzeń. Rozpoczynam parsowanie szczegółów...")
        
        all_events_data = []
        
        for url in event_urls:
            event_data = scrape_event_details(session, url)
            if event_data:
                all_events_data.append(event_data)
                
        return all_events_data


def run_scraper_job(is_first_run: bool = False):
    logging.info("--- Rozpoczęcie sprawdzania wydarzeń ---")
    start_time = datetime.now()
    try:
        results = scrape_arena_events()
        logging.info(f"Znaleziono {len(results)} wydarzeń.")
        
        with sqlite3.connect(DB_FILE) as conn:
            for event in results:
                event_id = upsert_event(conn, event, is_first_run)
                save_snapshot(conn, event_id, event.get("tickets_available"))
    except Exception as e:
        logging.error(f"Wystąpił błąd podczas działania scrapera: {e}")
        logging.debug(traceback.format_exc())
    finally:
        end_time = datetime.now()
        logging.info(f"--- Zakończenie sprawdzania (Czas trwania: {end_time - start_time}) ---")

if __name__ == "__main__":
    init_db()
    
    # Pobranie interwału z env (domyślnie 10)
    try:
        interval_minutes = int(os.environ.get("SCRAPE_INTERVAL_MINUTES", 10))
    except ValueError:
        logging.warning("Nieprawidłowa wartość zmiennej SCRAPE_INTERVAL_MINUTES, używam domyślnej 10.")
        interval_minutes = 10

    # Pierwsze uruchomienie przy starcie
    run_scraper_job(is_first_run=True)
    
    logging.info(f"Uruchamiam scheduler z interwałem {interval_minutes} minut...")
    scheduler = BlockingScheduler()
    scheduler.add_job(lambda: run_scraper_job(is_first_run=False), 'interval', minutes=interval_minutes)
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logging.info("Zatrzymano scheduler.")
