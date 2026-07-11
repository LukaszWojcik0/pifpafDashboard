import hashlib
import json
import logging
import os
import re
import sqlite3
import socket
import threading
import time
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from alerts import send_alert
from db import acquire_scrape_lease, finish_scraper_run, get_connection, release_scrape_lease, start_scraper_run, update_event
from request_security import (
    URLBlockedError,
    build_request_policy,
    normalize_url_for_request,
    safe_get,
    sanitize_url_for_log,
    split_header_controls,
    validate_url_for_request,
)

logger = logging.getLogger(__name__)
_RUN_LOCK = threading.Lock()

DEFAULT_EVENT_LINK_SELECTOR = 'a[href*="/produkt/"], a[href*="/wydarzenie/"], a[href*="/events/"]'
DEFAULT_TICKETS_REGEX = r'\((\d+)\s+dost(?:epnych|ępnych|Ä™pnych)\)'
DEFAULT_SOLD_OUT_REGEX = r'wyprzedane|brak biletow|brak biletów|brak w magazynie|sprzedaz zamknieta|sprzedaż zamknięta'
EVENT_PATH_RE = re.compile(r'^/(?:produkt|wydarzenie|events)/[^/]', re.IGNORECASE)
TRACKING_QUERY_PREFIXES = ('utm_',)
TRACKING_QUERY_KEYS = {'fbclid', 'gclid', 'mc_cid', 'mc_eid'}

# Słownik przechowujący ostatnią widoczną liczbę biletów w pamięci
last_known_tickets = {}

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


def scrape_event_details(html_content, event_url, config):
    soup = BeautifulSoup(html_content or '', 'html.parser')
    if is_antibot_page(html_content):
        return {
            'title': None,
            'url': event_url,
            'date': None,
            'time': None,
            'tickets_available': None,
            'status': 'Nieznany',
            'image_url': None,
            'measurement_known': False,
            'rejection_reason': 'antibot_page',
        }

    title_selector = config.get('title_selector') if config else None
    title_element = safe_select_one(soup, title_selector, 'title') if title_selector else soup.find('h1')
    title = title_element.get_text(strip=True) if title_element else None
    date = first_text(soup, config.get('date_selector'), re.compile(r'date|data', re.I), 'date') if config else None
    time_value = first_text(soup, config.get('time_selector'), re.compile(r'time|czas|godzina', re.I), 'time') if config else None
    image_url = first_image_url(soup, event_url, config.get('image_selector') if config else None)
    page_text = soup.get_text(separator=' ', strip=True)
    tickets = parse_ticket_count(
        page_text,
        config.get('tickets_regex') if config else None,
        config.get('sold_out_regex') if config else None,
    )

    return {
        'title': title,
        'url': event_url,
        'date': date,
        'time': time_value,
        'tickets_available': tickets.value,
        'status': tickets.status,
        'image_url': image_url,
        'measurement_known': tickets.known,
        'rejection_reason': tickets.reason,
    }


def get_by_path(data, path_str):
    if not path_str:
        return data
    keys = path_str.replace('[', '.').replace(']', '').split('.')
    value = data
    try:
        for key in keys:
            if not key:
                continue
            if isinstance(value, list):
                value = value[int(key)]
            else:
                value = value.get(key)
        return value
    except Exception:
        return None


def int_or_unknown(value):
    if value is None:
        return TicketParseResult(False, None, 'Nieznany', 'tickets_not_found')
    try:
        return TicketParseResult(True, int(value), 'Bilety dostepne' if int(value) > 0 else 'Wyprzedane')
    except (TypeError, ValueError):
        return TicketParseResult(False, None, 'Nieznany', 'tickets_not_numeric')


def build_api_event(evt, source, list_url, custom_headers, request_policy):
    title = get_by_path(evt, source.get('title_selector')) or 'Nieznane Wydarzenie API'
    date = get_by_path(evt, source.get('date_selector'))
    time_value = get_by_path(evt, source.get('time_selector'))
    image = get_by_path(evt, source.get('image_selector'))
    tickets = int_or_unknown(get_by_path(evt, source.get('tickets_regex')))
    event_url_id = get_by_path(evt, source.get('sold_out_regex'))

    if date and isinstance(date, str) and 'T' in date:
        date = date.split('T')[0]
    if time_value and isinstance(time_value, str) and 'T' in time_value:
        time_value = time_value.split('T')[1][:5]

    if str(event_url_id).startswith('http'):
        event_url = normalize_url(str(event_url_id), list_url)
    elif 'playair.pro' in list_url:
        state = normalize_playair_string(get_by_path(evt, 'arena.address.state'))
        city = normalize_playair_string(get_by_path(evt, 'arena.address.city'))
        alias = get_by_path(evt, 'arena.alias') or 'arena'
        event_url = normalize_url(f'https://playair.pro/arena/{state}/{city}/{alias}/event/{event_url_id}', list_url)
        img_id = get_by_path(evt, 'additionalPicturesIds[0]') or get_by_path(evt, 'pictureId')
        if img_id:
            image = f'https://api.playair.pro/files/production/{img_id}/image.jpg'
    else:
        event_url = normalize_url(f'{list_url}#{event_url_id or hashlib.md5(str(title).encode()).hexdigest()}', list_url)

    if 'playair.pro' in list_url and event_url_id:
        parts_url = f'https://api.playair.pro/api/user-consent/{event_url_id}'
        parts_resp = safe_get(parts_url, retries=1, custom_headers=custom_headers, policy=request_policy)
        if parts_resp:
            try:
                parts_data = json.loads(parts_resp)
                if isinstance(parts_data, list):
                    tickets = TicketParseResult(True, len(parts_data), 'Bilety dostepne' if len(parts_data) > 0 else 'Wyprzedane')
                elif isinstance(parts_data, dict):
                    ticket_path = source.get('tickets_regex')
                    if ticket_path:
                        tickets = int_or_unknown(get_by_path(parts_data, ticket_path))
                    elif 'content' in parts_data and isinstance(parts_data['content'], list):
                        tickets = TicketParseResult(True, len(parts_data['content']), 'Bilety dostepne' if parts_data['content'] else 'Wyprzedane')
            except Exception as exc:
                logger.warning('Could not parse PlayAir participants for %s: %s', event_url, exc)

    try:
        validate_url_for_request(normalize_url_for_request(event_url), request_policy)
    except URLBlockedError as exc:
        raise URLBlockedError(f'Blocked event URL {sanitize_url_for_log(event_url)}: {exc}') from exc

    if event_url.startswith('http'):
        event_html = safe_get(event_url, retries=1, custom_headers=custom_headers, policy=request_policy)
        if event_html:
            html_data = scrape_event_details(event_html, event_url, source)
            if not image or 'playair' not in list_url:
                image = html_data.get('image_url') or image

    return {
        'id': event_id_for_url(event_url),
        'title': str(title),
        'link': event_url,
        'date_info': f'{date or ""} {time_value or ""}'.strip() or 'Brak daty',
        'available_places': tickets.value,
        'measurement_known': tickets.known,
        'rejection_reason': tickets.reason,
        'image_url': str(image) if image else None,
        'custom_ntfy_url': source.get('ntfy_url'),
        'custom_ntfy_template': source.get('ntfy_template'),
    }


def save_event(event, summary, is_first_run):
    is_new, max_available, measurement_known = update_event(
        event['id'],
        event['title'],
        event['link'],
        event['date_info'],
        event['available_places'] if event['measurement_known'] else None,
        event.get('image_url'),
    )

    if is_new:
        summary.created += 1
    else:
        summary.updated += 1
    if measurement_known:
        summary.valid += 1
    else:
        summary.rejected += 1
        logger.info('Rejected measurement for %s: %s', event['link'], event.get('rejection_reason'))

    if is_first_run or not measurement_known:
        return

    title = event['title']
    custom_url = event.get('custom_ntfy_url')
    custom_template = event.get('custom_ntfy_template')
    if custom_template:
        msg = custom_template.replace('{title}', str(title)).replace('{available}', str(event['available_places'])).replace('{max}', str(max_available))
    else:
        msg = f'dostepna ilosc biletow: {event["available_places"]}/{max_available}'

    should_alert = is_new or (event['available_places'] is not None and 0 < event['available_places'] < 5)
    if not should_alert:
        return

    if custom_url:
        try:
            validate_url_for_request(custom_url, build_request_policy(custom_url))
            tags = 'new,tada' if is_new else 'warning'
            headers = {'Title': title.encode('utf-8'), 'Click': event['link'], 'Tags': tags}
            requests.post(custom_url, data=msg.encode('utf-8'), headers=headers, timeout=5)
        except Exception as exc:
            logger.error('Error sending custom ntfy for %s to %s: %s', title, sanitize_url_for_log(custom_url), exc)
    else:
        send_alert(title, msg, tags=['new', 'tada'] if is_new else ['warning'])


def active_sources():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    sources = [dict(row) for row in cursor.execute('SELECT * FROM scraping_sources WHERE is_active = 1').fetchall()]
    conn.close()
    return sources


def parse_custom_headers(source):
    if not source.get('request_headers'):
        return None, {}
    try:
        raw_headers = json.loads(source['request_headers'])
        if not isinstance(raw_headers, dict):
            logger.warning('Ignoring non-object request headers for %s', source.get('name'))
            return None, {}
        headers, controls = split_header_controls(raw_headers)
        return headers, controls
    except Exception as exc:
        logger.error('Could not parse request headers for %s: %s', source.get('name'), exc)
        return None, {}


def process_api_source(source, list_url, custom_headers, request_policy, summary, is_first_run):
    if '{TODAY}' in list_url:
        list_url = list_url.replace('{TODAY}', datetime.now().strftime('%Y-%m-%dT00:00:00.000Z'))

    response_text = safe_get(list_url, custom_headers=custom_headers, policy=request_policy)
    if not response_text:
        logger.warning('Could not fetch API data: %s', list_url)
        return

    try:
        api_data = json.loads(response_text)
    except Exception as exc:
        logger.error('Could not parse JSON from %s: %s', list_url, exc)
        return

    events_list_path = source.get('list_links_selector')
    events_array = get_by_path(api_data, events_list_path) if events_list_path else api_data
    if not isinstance(events_array, list):
        events_array = [events_array] if isinstance(events_array, dict) else []

    logger.info('Found %s JSON events for %s.', len(events_array), source.get('name'))
    summary.found += len(events_array)

    for evt in events_array:
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
                # Wysyłaj alert tylko jeśli ilość biletów zmieniła się od ostatniego sprawdzenia
                if last_known_tickets.get(event['id']) != event['available_places']:
                    send_alert(title, msg, tags=["warning"])
            
            last_known_tickets[event['id']] = event['available_places']
        except Exception as e:
            logger.error(f"Error updating event {event['title']}: {e}")
            
    logger.info("Scrape run completed.")
