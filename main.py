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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}
DB_FILE = os.environ.get("DATABASE_PATH", "events.db")

# Słownik do śledzenia anomalii (ile razy pod rząd było 0 lub None)
anomaly_strikes: Dict[str, int] = {}
MAX_ANOMALY_STRIKES = 2

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
                status TEXT,
                image_url TEXT
            )
        ''')
        # Add image_url to existing events table if not exists, for backwards compatibility
        try:
            # This will fail if the column already exists (e.g. table was just created), which is fine.
            cursor.execute('ALTER TABLE events ADD COLUMN image_url TEXT')
            logging.info("Dodano kolumnę 'image_url' do tabeli 'events' dla istniejącej bazy danych.")
        except sqlite3.OperationalError:
            pass  # Column already exists

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
                is_active INTEGER DEFAULT 1
            )
        ''')
        cursor.execute("SELECT count(*) FROM scraping_sources")
        if cursor.fetchone()[0] == 0:
            logging.info("Brak źródeł skrapowania. Inicjowanie domyślnym źródłem: Arena Walki.")
            cursor.execute('''
                INSERT INTO scraping_sources 
                (name, list_url, list_links_selector, title_selector, date_selector, time_selector, image_selector, tickets_regex, sold_out_regex)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', ('Arena Walki', 'https://arenawalki.pl/gry-otwarte/', 'a[href*="/produkt/"], a[href*="/wydarzenie/"]', 'h1', '[class*="date"], [class*="data"]', '[class*="time"], [class*="czas"], [class*="godzina"]', 'meta[property="og:image"], .wp-post-image, .woocommerce-product-gallery__image img', r'\((\d+)\s+dostępnych\)', r'wyprzedane|brak biletów|brak w magazynie|sprzedaż zamknięta'))

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
    image_url = event.get("image_url")

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
            INSERT INTO events (url, title, event_date, event_time, max_available, first_seen, last_seen, status, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (url, title, event_date, event_time, max_available, now, now, status, image_url))
        event_id = cursor.lastrowid
    else:
        event_id, current_max_available, previous_status = row
        max_available = current_max_available
        if available is not None and (current_max_available is None or available > current_max_available):
            max_available = available
        
        cursor.execute('''
            UPDATE events
            SET title = ?, event_date = ?, event_time = ?, status = ?, last_seen = ?, max_available = ?, image_url = ?
            WHERE id = ?
        ''', (title, event_date, event_time, status, now, max_available, image_url, event_id))
        
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

def get_event_urls(session: requests.Session, list_url: str, link_selector: str = None) -> List[str]:
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

    try:
        links_elements = soup.select(link_selector) if link_selector else soup.find_all('a', href=True)
        for link in links_elements:
            if not link.has_attr('href'):
                continue
            href = link['href']
            text = link.get_text(separator=' ', strip=True).lower()
            
            # Dodatkowy fallback logiki tekstowej, jeśli selektor był pusty
            if link_selector or "dołącz" in text or "kup" in text or "bilet" in text or "/produkt/" in href or "/wydarzenie/" in href:
                full_url = urljoin(list_url, href)
                if full_url != list_url:
                    event_urls.add(full_url)
    except Exception as e:
        logging.error(f"Błąd przetwarzania selektora linków: {e}")

    return list(event_urls)

def scrape_event_details(session: requests.Session, event_url: str, config: Dict) -> Optional[Dict]:
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
        "status": "Nieznany",
        "image_url": None
    }

    # Title
    title_element = soup.select_one(config.get('title_selector')) if config.get('title_selector') else soup.find('h1')
    if title_element:
        data["title"] = title_element.get_text(strip=True)

    # Image
    if config.get('image_selector'):
        for selector in config['image_selector'].split(','):
            img_element = soup.select_one(selector.strip())
            if img_element:
                if img_element.name == 'meta' and img_element.get('content'):
                    data['image_url'] = img_element['content']
                    break
                elif img_element.name == 'img' and img_element.get('src'):
                    data['image_url'] = urljoin(event_url, img_element['src'])
                    break
    else:
        og_image_meta = soup.find('meta', property='og:image')
        if og_image_meta and og_image_meta.get('content'):
            data['image_url'] = og_image_meta['content']

    # Date
    date_element = soup.select_one(config.get('date_selector')) if config.get('date_selector') else soup.find(class_=re.compile(r'date|data', re.I))
    if date_element:
        data["date"] = date_element.get_text(strip=True)

    # Time
    time_element = soup.select_one(config.get('time_selector')) if config.get('time_selector') else soup.find(class_=re.compile(r'time|czas|godzina', re.I))
    if time_element:
        data["time"] = time_element.get_text(strip=True)

    # Tickets & Status Regex Matcher
    page_text = soup.get_text(separator=' ', strip=True)
    tickets_regex = config.get('tickets_regex') or r'\((\d+)\s+dostępnych\)'
    soldout_regex = config.get('sold_out_regex') or r'wyprzedane|brak biletów|brak w magazynie|sprzedaż zamknięta'

    tickets_match = re.search(tickets_regex, page_text, re.IGNORECASE)
    
    if tickets_match:
        data["tickets_available"] = int(tickets_match.group(1))
        data["status"] = "Bilety dostępne"
    else:
        if re.search(soldout_regex, page_text, re.IGNORECASE):
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
    all_events_data = []
    with requests.Session() as session:
        session.headers.update(HEADERS)
        
        sources = []
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            sources = [dict(row) for row in cursor.execute("SELECT * FROM scraping_sources WHERE is_active = 1").fetchall()]

        for source in sources:
            list_url = source['list_url']
            logging.info(f"=== Rozpoczynam pobieranie z źródła: {source['name']} ({list_url}) ===")
            
            event_urls = get_event_urls(session, list_url, source.get('list_links_selector'))
            
            if not event_urls:
                logging.warning(f"Nie znaleziono żadnych wydarzeń na stronie {source['name']}.")
                continue
                
            logging.info(f"Znaleziono {len(event_urls)} potencjalnych wydarzeń na stronie {source['name']}. Analiza...")
            
            for url in event_urls:
                event_data = scrape_event_details(session, url, source)
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
                url = event.get("url")
                avail = event.get("tickets_available")
                
                # Weryfikacja anomalii: jeśli biletów jest 0 lub None, czekamy na potwierdzenie w kolejnych pobraniach
                if avail == 0 or avail is None:
                    strikes = anomaly_strikes.get(url, 0)
                    if strikes < MAX_ANOMALY_STRIKES:
                        anomaly_strikes[url] = strikes + 1
                        logging.warning(f"Zignorowano nagły spadek biletów do 0/None dla: '{event.get('title')}'. Próba {strikes + 1}/{MAX_ANOMALY_STRIKES}")
                        continue # Pomijamy zapis do bazy i ntfy w tym cyklu
                    else:
                        # Zostawiamy wartość - anomalia powtórzyła się wystarczająco dużo razy
                        pass
                else:
                    # Normalna wartość (>0) - resetujemy licznik błędów dla tego eventu
                    if url in anomaly_strikes:
                        anomaly_strikes[url] = 0
                        
                event_id = upsert_event(conn, event, is_first_run)
                save_snapshot(conn, event_id, avail)
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
        interval_minutes = int(os.environ.get("SCRAPE_INTERVAL_MINUTES", 1))
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
