import requests
from bs4 import BeautifulSoup
import logging
import hashlib
import time
import re
import sqlite3
from urllib.parse import urljoin
import json
from datetime import datetime
from db import update_event, get_connection
from alerts import send_alert

logger = logging.getLogger(__name__)

import unicodedata
def normalize_playair_string(text):
    if not text: return ""
    text = str(text).lower()
    replacements = {'ą':'a', 'ć':'c', 'ę':'e', 'ł':'l', 'ń':'n', 'ó':'o', 'ś':'s', 'ź':'z', 'ż':'z'}
    for k, v in replacements.items():
        text = text.replace(k, v)
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r'[^a-z0-9]+', '-', text).strip('-')
    return text

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
        is_api = source.get('is_api') == 1
        
        if is_api:
            if "{TODAY}" in list_url:
                list_url = list_url.replace("{TODAY}", datetime.now().strftime('%Y-%m-%dT00:00:00.000Z'))
                
            logger.info(f"=== Rozpoczynam pobieranie (API JSON) z: {source['name']} ({list_url}) ===")
            response_text = get_page_with_retry(list_url)
            if not response_text:
                logger.warning(f"Nie udało się pobrać danych API: {list_url}")
                continue
            
            try:
                api_data = json.loads(response_text)
            except Exception as e:
                logger.error(f"Nie udało się sparsować JSON z {list_url}: {e}")
                continue
                
            def get_by_path(d, path_str):
                if not path_str: return d
                keys = path_str.replace('[', '.').replace(']', '').split('.')
                val = d
                try:
                    for k in keys:
                        if not k: continue
                        if isinstance(val, list):
                            val = val[int(k)]
                        else:
                            val = val.get(k)
                    return val
                except Exception:
                    return None

            events_list_path = source.get('list_links_selector')
            events_array = get_by_path(api_data, events_list_path) if events_list_path else api_data
            
            if not isinstance(events_array, list):
                events_array = [events_array] if isinstance(events_array, dict) else []
                    
            logger.info(f"Znaleziono {len(events_array)} wydarzeń w JSON.")
            
            for evt in events_array:
                title = get_by_path(evt, source.get('title_selector')) or "Nieznane Wydarzenie API"
                date = get_by_path(evt, source.get('date_selector'))
                time_val = get_by_path(evt, source.get('time_selector'))
                image = get_by_path(evt, source.get('image_selector'))
                tickets = get_by_path(evt, source.get('tickets_regex'))
                
                if date and isinstance(date, str) and 'T' in date:
                    date = date.split('T')[0]
                if time_val and isinstance(time_val, str) and 'T' in time_val:
                    time_val = time_val.split('T')[1][:5]
                    
                evt_url_id = get_by_path(evt, source.get('sold_out_regex'))
                
                if str(evt_url_id).startswith('http'):
                    evt_url = evt_url_id
                else:
                    if "playair.pro" in list_url:
                        state = normalize_playair_string(get_by_path(evt, "arena.address.state"))
                        city = normalize_playair_string(get_by_path(evt, "arena.address.city"))
                        alias = get_by_path(evt, "arena.alias") or "arena"
                        evt_url = f"https://playair.pro/arena/{state}/{city}/{alias}/event/{evt_url_id}"
                        
                        img_id = get_by_path(evt, "additionalPicturesIds[0]") or get_by_path(evt, "pictureId")
                        if img_id:
                            image = f"https://api.playair.pro/files/production/{img_id}/image.jpg"
                    else:
                        evt_url = f"{list_url}#{evt_url_id or hashlib.md5(str(title).encode()).hexdigest()}"
                    
                tickets_available = int(tickets) if tickets is not None and str(tickets).isdigit() else 0
                
                if "playair.pro" in list_url:
                    # Dociągamy faktyczną liczbę zapisanych graczy!
                    parts_url = f"https://api.playair.pro/api/event/{evt_url_id}/participants"
                    parts_resp = get_page_with_retry(parts_url, retries=1)
                    if parts_resp:
                        try:
                            parts_data = json.loads(parts_resp)
                            if isinstance(parts_data, list):
                                tickets_available = len(parts_data)
                            elif isinstance(parts_data, dict) and 'content' in parts_data:
                                tickets_available = len(parts_data['content'])
                        except:
                            pass

                # Zgodnie z prośbą - po dodatkowe braki ze zdjęciami idziemy klasycznie na stronę HTML
                if evt_url.startswith('http'):
                    event_html = get_page_with_retry(evt_url, retries=1)
                    if event_html:
                        html_data = scrape_event_details(event_html, evt_url, source)
                        if not image or "playair" not in list_url:
                            image = html_data.get('image_url') or image

                all_events.append({
                    'id': hashlib.md5(str(evt_url).encode('utf-8')).hexdigest(),
                    'title': str(title),
                    'link': str(evt_url),
                    'date_info': f"{date or ''} {time_val or ''}".strip() or "Brak daty",
                    'available_places': tickets_available,
                    'image_url': str(image) if image else None,
                    'custom_ntfy_url': source.get('ntfy_url'),
                    'custom_ntfy_template': source.get('ntfy_template')
                })
            continue # Omijamy HTMLowe parsowanie poniżej dla tego źródła!

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
                'image_url': image_url,
                'custom_ntfy_url': source.get('ntfy_url'),
                'custom_ntfy_template': source.get('ntfy_template')
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
            
            title = event['title']
            custom_url = event.get('custom_ntfy_url')
            custom_template = event.get('custom_ntfy_template')
            
            # Custom msg logic
            if custom_template:
                msg = custom_template.replace('{title}', str(title)).replace('{available}', str(event['available_places'])).replace('{max}', str(max_avail))
            else:
                msg = f"dostepna ilosc biletów: {event['available_places']}/{max_avail}"
            
            # Wysyłka powiadomienia
            if not is_first_run:
                should_alert = is_new or (event['available_places'] > 0 and event['available_places'] < 5)
                if should_alert:
                    if custom_url:
                        try:
                            tags = "new,tada" if is_new else "warning"
                            headers = {"Title": title.encode('utf-8'), "Click": event['link'], "Tags": tags}
                            requests.post(custom_url, data=msg.encode('utf-8'), headers=headers, timeout=5)
                        except Exception as e:
                            logger.error(f"Błąd wysyłania custom ntfy dla {title}: {e}")
                    else:
                        # Fallback to default alerts.py logic
                        send_alert(title, msg, tags=["new", "tada"] if is_new else ["warning"])
        except Exception as e:
            logger.error(f"Error updating event {event['title']}: {e}")
            
    logger.info("Scrape run completed.")
