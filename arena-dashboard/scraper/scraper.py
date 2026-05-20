import requests
from bs4 import BeautifulSoup
import logging
import hashlib
import time
from db import update_event
from alerts import send_alert

logger = logging.getLogger(__name__)

BASE_URL = 'https://arenawalki.pl/gry-otwarte/'
DOMAIN_URL = 'https://arenawalki.pl'

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

def extract_tickets(detail_html):
    if not detail_html:
        return 0
    soup = BeautifulSoup(detail_html, 'html.parser')
    available_places = 0
    left_span = soup.find('span', class_='aev-left')
    if left_span:
        text = left_span.text.lower()
        digits = ''.join(filter(str.isdigit, text))
        if digits:
            available_places = int(digits)
    return available_places

def parse_events(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    events = []
    
    event_elements = soup.find_all('article', class_=lambda c: c and 'event-card' in c)
    
    for el in event_elements:
        try:
            title_el = el.find('h3', class_=lambda c: c and 'event-card__title' in c)
            title = title_el.text.strip() if title_el else "Nieznane wydarzenie"
            
            date_el = el.find('div', class_=lambda c: c and 'event-card__date' in c)
            date_info = date_el.text.strip() if date_el else "Unknown Date"
            
            link_el = el.find('a', class_=lambda c: c and 'event-card__cta' in c)
            link = link_el['href'] if link_el and 'href' in link_el.attrs else ""
            
            img_el = el.find('img')
            image_url = img_el['src'] if img_el and 'src' in img_el.attrs else None
            
            if link and not link.startswith('http'):
                link = DOMAIN_URL.rstrip('/') + '/' + link.lstrip('/')
                
            if title and len(title) > 3 and link:
                event_id = hashlib.md5(link.encode('utf-8')).hexdigest()
                
                logger.info(f"Wydarzenie: '{title}' | Znaleziony URL obrazka: {image_url}")

                # Fetch details page to get tickets
                logger.info(f"Fetching details for {title}...")
                detail_html = get_page_with_retry(link)
                available_places = extract_tickets(detail_html)
                
                events.append({
                    'id': event_id,
                    'title': title,
                    'link': link,
                    'date_info': date_info,
                    'available_places': available_places,
                    'image_url': image_url
                })
                # Prevent rate limiting
                time.sleep(1)
        except Exception as e:
            logger.debug(f"Skipping element due to parsing error: {e}")
            continue

    unique_events = {e['id']: e for e in events}.values()
    return list(unique_events)

def run_scraper(is_first_run=False):
    logger.info("Starting scrape run...")
    html = get_page_with_retry(BASE_URL)
    
    if not html:
        logger.error("Skipping run due to fetch failure.")
        return

    events = parse_events(html)
    logger.info(f"Found {len(events)} events.")
    
    for event in events:
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
