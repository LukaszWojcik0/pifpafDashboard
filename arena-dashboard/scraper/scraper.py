import re
import logging
from typing import List, Dict, Optional
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import time

logger = logging.getLogger(__name__)

BASE_URL = "https://arenawalki.pl/gry-otwarte/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}

def get_event_urls(session: requests.Session, list_url: str) -> List[str]:
    try:
        response = session.get(list_url, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Błąd HTTP podczas pobierania listy wydarzeń z {list_url}: {e}")
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

def scrape_event_details(session: requests.Session, event_url: str, retries: int = 3) -> Optional[Dict]:
    for attempt in range(retries):
        try:
            response = session.get(event_url, timeout=15)
            response.raise_for_status()
            break
        except requests.RequestException as e:
            logger.warning(f"Błąd pobierania {event_url} (próba {attempt + 1}/{retries}): {e}")
            if attempt == retries - 1:
                return None
            time.sleep(2)

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
    with requests.Session() as session:
        session.headers.update(HEADERS)
        
        logger.info(f"Rozpoczynam pobieranie linków z: {BASE_URL}")
        event_urls = get_event_urls(session, BASE_URL)
        
        if not event_urls:
            logger.warning("Nie znaleziono wydarzeń na stronie głównej.")
            return []
            
        logger.info(f"Znaleziono {len(event_urls)} wydarzeń. Pobieranie detali...")
        
        all_events_data = []
        for url in event_urls:
            event_data = scrape_event_details(session, url)
            if event_data:
                all_events_data.append(event_data)
                
        return all_events_data
