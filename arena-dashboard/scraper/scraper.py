import requests
from bs4 import BeautifulSoup
import logging
import hashlib
import time
import re
import sqlite3
from urllib.parse import urljoin
from db import update_event, get_connection
from alerts import send_alert

logger = logging.getLogger(__name__)

def get_page_with_retry(url, retries=3, backoff_factor=1):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    for i in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            logger.warning(f"Attempt {i+1} failed to fetch {url}: {e}")
            if i < retries - 1:
                time.sleep(backoff_factor * (2 ** i))
    logger.error(f"Failed to fetch {url} after {retries} retries.")
    return None

def get_event_urls(html_content, list_url, link_selector):
    soup = BeautifulSoup(html_content, 'html.parser')
    event_urls = set()
    
    try:
        links_elements = soup.select(link_selector) if link_selector else soup.find_all('a', href=True)
        for link in links_elements:
            if not link.has_attr('href'):
                continue
            href = link['href']
            text = link.get_text(separator=' ', strip=True).lower()
            
            if link_selector or "dołącz" in text or "kup" in text or "bilet" in text or "/produkt/" in href or "/wydarzenie/" in href:
                full_url = urljoin(list_url, href)
                if full_url != list_url:
                    event_urls.add(full_url)
    except Exception as e:
        logger.error(f"Błąd przetwarzania selektora linków: {e}")
        
    return list(event_urls)

def scrape_event_details(html_content, event_url, config):
    soup = BeautifulSoup(html_content, 'html.parser')
    data = {
        "title": None,
        "url": event_url,
        "date": None,
        "time": None,
        "tickets_available": 0,
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
    if not data['image_url']:
        og_image_meta = soup.find('meta', property='og:image')
        if og_image_meta and og_image_meta.get('content'):
            data['image_url'] = og_image_meta['content']

    # Date & Time
    date_element = soup.select_one(config.get('date_selector')) if config.get('date_selector') else soup.find(class_=re.compile(r'date|data', re.I))
    if date_element:
        data["date"] = date_element.get_text(strip=True)

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
            
    return data

def run_scraper(is_first_run=False):
    logger.info("Starting scrape run...")
    
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    sources = [dict(row) for row in cursor.execute("SELECT * FROM scraping_sources WHERE is_active = 1").fetchall()]
    conn.close()

    all_events = []

    for source in sources:
        list_url = source['list_url']
        logger.info(f"=== Rozpoczynam pobieranie z źródła: {source['name']} ({list_url}) ===")
        list_html = get_page_with_retry(list_url)
        if not list_html:
            logger.warning(f"Nie udało się pobrać listy z {list_url}")
            continue

        event_urls = get_event_urls(list_html, list_url, source.get('list_links_selector'))
        if not event_urls:
            logger.info(f"Nie znaleziono pod-linków do wydarzeń na stronie {source['name']}. Próba analizy wskazanego URL bezpośrednio jako pojedyncze wydarzenie...")
            event_urls = [list_url]

        logger.info(f"Znaleziono {len(event_urls)} potencjalnych wydarzeń. Analiza...")

        for url in event_urls:
            event_html = get_page_with_retry(url)
            if not event_html:
                continue

            event_data = scrape_event_details(event_html, url, source)
            title = event_data['title'] or "Nieznane wydarzenie"
            image_url = event_data['image_url']
            logger.info(f"Wydarzenie: '{title}' | Znaleziony URL obrazka: {image_url}")

            event_id = hashlib.md5(url.encode('utf-8')).hexdigest()
            date_info = f"{event_data['date'] or ''} {event_data['time'] or ''}".strip()
            if not date_info:
                date_info = "Unknown Date"

            all_events.append({
                'id': event_id,
                'title': title,
                'link': url,
                'date_info': date_info,
                'available_places': event_data['tickets_available'],
                'image_url': image_url
            })
            time.sleep(1)

    logger.info(f"Zakończono odpytywanie. Zaktualizowanych zostanie {len(all_events)} wydarzeń.")
    
    for event in all_events:
        try:
            is_new, max_avail = update_event(
                event['id'], 
                event['title'], 
                event['link'], 
                event['date_info'], 
                event['available_places'],
                event.get('image_url')
            )
            
            # Alerting logic requested format
            # title: nazwa wydarzenia
            # opis: dostepna ilosc biletów: dostępne/max
            
            msg = f"dostepna ilosc biletów: {event['available_places']}/{max_avail}"
            title = event['title']
            
            if is_new and not is_first_run:
                send_alert(title, msg, tags=["new", "tada"])
            elif not is_first_run and event['available_places'] > 0 and event['available_places'] < 5:
                 send_alert(title, msg, tags=["warning"])
        except Exception as e:
            logger.error(f"Error updating event {event['title']}: {e}")
            
    logger.info("Scrape run completed.")
