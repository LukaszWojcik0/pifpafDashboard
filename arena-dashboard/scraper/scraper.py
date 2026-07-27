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
from db import (
    acquire_scrape_lease,
    finish_scraper_run,
    get_connection,
    get_scrape_lease_state,
    release_scrape_lease,
    renew_scrape_lease,
    start_scraper_run,
    update_event,
)
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
POLISH_MONTHS = {
    'stycznia': 1,
    'lutego': 2,
    'marca': 3,
    'kwietnia': 4,
    'maja': 5,
    'czerwca': 6,
    'lipca': 7,
    'sierpnia': 8,
    'wrzesnia': 9,
    'września': 9,
    'pazdziernika': 10,
    'października': 10,
    'listopada': 11,
    'grudnia': 12,
}


@dataclass
class TicketParseResult:
    known: bool
    value: int | None
    status: str
    reason: str | None = None


@dataclass
class ScrapeSummary:
    sources: int = 0
    found: int = 0
    valid: int = 0
    rejected: int = 0
    created: int = 0
    updated: int = 0
    skipped: bool = False

    def as_dict(self):
        return {
            'sources': self.sources,
            'found': self.found,
            'valid': self.valid,
            'rejected': self.rejected,
            'created': self.created,
            'updated': self.updated,
            'skipped': self.skipped,
        }


def normalize_playair_string(text):
    if not text:
        return ''
    value = str(text).lower()
    replacements = {'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z'}
    for source, target in replacements.items():
        value = value.replace(source, target)
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('utf-8')
    return re.sub(r'[^a-z0-9]+', '-', value).strip('-')


def normalize_url(url, base_url):
    joined = urljoin(base_url, (url or '').strip())
    parsed = urlparse(joined)
    scheme = (parsed.scheme or 'https').lower()
    netloc = parsed.netloc.lower()
    path = re.sub(r'/+', '/', parsed.path or '/')
    if path != '/':
        path = path.rstrip('/')
    query_items = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered in TRACKING_QUERY_KEYS or any(lowered.startswith(prefix) for prefix in TRACKING_QUERY_PREFIXES):
            continue
        query_items.append((key, value))
    query = urlencode(sorted(query_items), doseq=True)
    return urlunparse((scheme, netloc, path, '', query, ''))


def is_supported_event_url(url):
    return bool(EVENT_PATH_RE.search(urlparse(url).path))


def event_id_for_url(url):
    return hashlib.md5(url.encode('utf-8')).hexdigest()


def is_antibot_page(html_content):
    text = BeautifulSoup(html_content or '', 'html.parser').get_text(' ', strip=True).lower()
    needles = [
        'checking your browser',
        'just a moment',
        'captcha',
        'cloudflare',
        'access denied',
        'enable javascript',
        'verify you are human',
    ]
    return any(needle in text for needle in needles)


def get_page_with_retry(url, retries=3, backoff_factor=1, custom_headers=None):
    policy = build_request_policy(url)
    return safe_get(
        url,
        retries=retries,
        backoff_factor=backoff_factor,
        custom_headers=custom_headers,
        policy=policy,
    )


def parse_event_date_text(text):
    value = (text or '').strip()
    iso_match = re.search(r'\b(\d{4}-\d{2}-\d{2})\b', value)
    if iso_match:
        return iso_match.group(1)

    polish_match = re.search(
        r'\b(\d{1,2})\s+([A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ]+)\s+(\d{4})\b',
        value,
        re.IGNORECASE,
    )
    if not polish_match:
        return None

    day = int(polish_match.group(1))
    raw_month = polish_match.group(2).lower()
    normalized_month = normalize_playair_string(raw_month).replace('-', '')
    month = POLISH_MONTHS.get(raw_month) or POLISH_MONTHS.get(normalized_month)
    year = int(polish_match.group(3))
    if not month:
        return None
    return f'{year:04d}-{month:02d}-{day:02d}'


def candidate_context(link):
    node = link
    for _ in range(5):
        if not node:
            break
        text = node.get_text(' ', strip=True)
        if parse_event_date_text(text):
            return node
        if node.name in {'article', 'section', 'li', 'div'} and len(text) > 20:
            return node
        node = node.parent
    return link.parent or link


def event_candidate_from_link(link, list_url):
    href = link.get('href')
    if not href:
        return None
    normalized = normalize_url(href, list_url)
    if normalized == normalize_url(list_url, list_url) or not is_supported_event_url(normalized):
        return None

    context = candidate_context(link)
    context_text = context.get_text(' ', strip=True) if context else link.get_text(' ', strip=True)
    heading = context.find(['h1', 'h2', 'h3', 'h4']) if context else None
    title = heading.get_text(' ', strip=True) if heading else link.get_text(' ', strip=True)
    return {
        'url': normalized,
        'title': title or None,
        'date': parse_event_date_text(context_text),
    }


def get_event_candidates(html_content, list_url, link_selector=None):
    soup = BeautifulSoup(html_content or '', 'html.parser')
    selected = safe_select(soup, link_selector, 'event links') if link_selector else []
    default_candidates = soup.find_all('a', href=True)
    candidates = []
    by_url = {}

    for link in list(selected) + list(default_candidates):
        candidate = event_candidate_from_link(link, list_url)
        if not candidate:
            continue
        existing = by_url.get(candidate['url'])
        if existing:
            existing['title'] = existing.get('title') or candidate.get('title')
            existing['date'] = existing.get('date') or candidate.get('date')
            continue
        by_url[candidate['url']] = candidate
        candidates.append(candidate)

    return candidates


def safe_select(soup, selector, context):
    if not selector:
        return []
    try:
        return soup.select(selector)
    except Exception as exc:
        logger.warning('Invalid CSS selector for %s: %s', context, exc)
        return []


def safe_select_one(soup, selector, context):
    if not selector:
        return None
    try:
        return soup.select_one(selector)
    except Exception as exc:
        logger.warning('Invalid CSS selector for %s: %s', context, exc)
        return None


def get_event_urls(html_content, list_url, link_selector=None):
    soup = BeautifulSoup(html_content or '', 'html.parser')
    selected = safe_select(soup, link_selector, 'event links') if link_selector else []
    default_candidates = soup.find_all('a', href=True)
    event_urls = []
    seen = set()

    for link in list(selected) + list(default_candidates):
        href = link.get('href')
        if not href:
            continue
        normalized = normalize_url(href, list_url)
        text = link.get_text(separator=' ', strip=True).lower()
        keyword_match = any(keyword in text for keyword in ['dolacz', 'dołącz', 'kup', 'bilet'])
        if not (is_supported_event_url(normalized) or (link_selector and keyword_match)):
            continue
        if normalized == normalize_url(list_url, list_url):
            continue
        if normalized not in seen:
            seen.add(normalized)
            event_urls.append(normalized)

    return event_urls


def get_event_urls(html_content, list_url, link_selector=None):
    return [candidate['url'] for candidate in get_event_candidates(html_content, list_url, link_selector)]


def parse_ticket_count(page_text, tickets_regex=None, soldout_regex=None):
    tickets_pattern = tickets_regex or DEFAULT_TICKETS_REGEX
    soldout_pattern = soldout_regex or DEFAULT_SOLD_OUT_REGEX

    try:
        tickets_match = re.search(tickets_pattern, page_text, re.IGNORECASE)
    except re.error as exc:
        return TicketParseResult(False, None, 'Nieznany', f'invalid tickets_regex: {exc}')

    if tickets_match:
        groups = [group for group in tickets_match.groups() if group is not None] or [tickets_match.group(0)]
        raw_value = re.sub(r'\D+', '', groups[0])
        if raw_value == '':
            return TicketParseResult(False, None, 'Nieznany', 'tickets_regex matched without numeric group')
        return TicketParseResult(True, int(raw_value), 'Bilety dostepne')

    try:
        if re.search(soldout_pattern, page_text, re.IGNORECASE):
            return TicketParseResult(True, 0, 'Wyprzedane')
    except re.error as exc:
        return TicketParseResult(False, None, 'Nieznany', f'invalid sold_out_regex: {exc}')

    return TicketParseResult(False, None, 'Nieznany', 'tickets_not_found')


def first_text(soup, selector, fallback_regex, context):
    element = safe_select_one(soup, selector, context) if selector else None
    if not element and fallback_regex:
        element = soup.find(class_=fallback_regex)
    return element.get_text(strip=True) if element else None


def first_image_url(soup, event_url, image_selector=None):
    selectors = [selector.strip() for selector in (image_selector or '').split(',') if selector.strip()]
    selectors.extend(['meta[property="og:image"]', '.wp-post-image', '.woocommerce-product-gallery__image img'])
    for selector in selectors:
        element = safe_select_one(soup, selector, 'image') if selector else None
        if not element:
            continue
        if element.name == 'meta' and element.get('content'):
            return normalize_url(element['content'], event_url)
        if element.name == 'img' and element.get('src'):
            return normalize_url(element['src'], event_url)
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
    page_text = soup.get_text(separator=' ', strip=True)
    date = first_text(soup, config.get('date_selector'), re.compile(r'date|data', re.I), 'date') if config else None
    date = parse_event_date_text(date) or parse_event_date_text(page_text) or date
    time_value = first_text(soup, config.get('time_selector'), re.compile(r'time|czas|godzina', re.I), 'time') if config else None
    image_url = first_image_url(soup, event_url, config.get('image_selector') if config else None)
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


def configured_lease_seconds():
    explicit = os.getenv('SCRAPE_LEASE_SECONDS')
    if explicit:
        try:
            return max(30, int(explicit))
        except ValueError:
            logger.warning('Invalid SCRAPE_LEASE_SECONDS=%s; using interval-based default.', explicit)

    try:
        interval_minutes = int(os.getenv('SCRAPE_INTERVAL_MINUTES', '10'))
    except ValueError:
        interval_minutes = 10
    return max(120, min(1800, interval_minutes * 120))


def start_lease_renewal(owner, ttl_seconds):
    stop_event = threading.Event()
    interval = max(15, min(60, ttl_seconds // 3))

    def renew_loop():
        while not stop_event.wait(interval):
            if not renew_scrape_lease(owner, ttl_seconds=ttl_seconds):
                logger.warning('Could not renew scrape lease; another process may have taken ownership.')
                break

    thread = threading.Thread(target=renew_loop, name='scrape-lease-renewal', daemon=True)
    thread.start()
    return stop_event, thread


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
            event = build_api_event(evt, source, list_url, custom_headers, request_policy)
            save_event(event, summary, is_first_run)
        except URLBlockedError as exc:
            summary.rejected += 1
            logger.warning('Rejected API event from %s: %s', source.get('name'), exc)
        except Exception:
            summary.rejected += 1
            logger.exception('Failed to process API event from %s', source.get('name'))


def process_html_source(source, list_url, custom_headers, request_policy, summary, is_first_run):
    list_html = safe_get(list_url, custom_headers=custom_headers, policy=request_policy)
    if not list_html:
        logger.warning('Could not fetch list from %s', list_url)
        return
    if is_antibot_page(list_html):
        summary.rejected += 1
        logger.warning('Rejected source %s: antibot_page', source.get('name'))
        return

    event_candidates = get_event_candidates(list_html, list_url, source.get('list_links_selector'))
    if not event_candidates and is_supported_event_url(normalize_url(list_url, list_url)):
        event_candidates = [{'url': normalize_url(list_url, list_url), 'title': None, 'date': None}]

    logger.info('Found %s potential events for %s.', len(event_candidates), source.get('name'))
    summary.found += len(event_candidates)

    for candidate in event_candidates:
        event_url = candidate['url']
        try:
            event_html = safe_get(event_url, custom_headers=custom_headers, policy=request_policy)
            if not event_html:
                summary.rejected += 1
                logger.warning('Rejected event %s: fetch_failed', event_url)
                continue

            event_data = scrape_event_details(event_html, event_url, source)
            title = event_data['title'] or candidate.get('title') or 'Nieznane wydarzenie'
            event_date = event_data['date'] or candidate.get('date')
            if candidate.get('date') and not event_data['date']:
                logger.info('Using list date for %s: %s', event_url, candidate.get('date'))
            if not event_date:
                logger.warning(
                    'Missing event date for source=%s url=%s title=%s date_selector=%s time_selector=%s',
                    source.get('name'),
                    sanitize_url_for_log(event_url),
                    title,
                    source.get('date_selector'),
                    source.get('time_selector'),
                )
            date_info = f'{event_date or ""} {event_data["time"] or ""}'.strip() or 'Unknown Date'
            event = {
                'id': event_id_for_url(event_url),
                'title': title,
                'link': event_url,
                'date_info': date_info,
                'available_places': event_data['tickets_available'],
                'measurement_known': event_data['measurement_known'],
                'rejection_reason': event_data['rejection_reason'],
                'image_url': event_data['image_url'],
                'custom_ntfy_url': source.get('ntfy_url'),
                'custom_ntfy_template': source.get('ntfy_template'),
            }
            save_event(event, summary, is_first_run)
        except Exception:
            summary.rejected += 1
            logger.exception('Failed to process event %s', event_url)
        finally:
            time.sleep(1)


def run_scraper(is_first_run=False):
    summary = ScrapeSummary()
    run_id = None
    renewal = None
    if not _RUN_LOCK.acquire(blocking=False):
        summary.skipped = True
        logger.warning('Scrape run skipped because another run is active in this process.')
        return summary.as_dict()

    lease_owner = f'{socket.gethostname()}:{os.getpid()}:{uuid.uuid4()}'
    lease_seconds = configured_lease_seconds()
    try:
        if not acquire_scrape_lease(lease_owner, ttl_seconds=lease_seconds):
            summary.skipped = True
            lease = get_scrape_lease_state()
            logger.warning(
                'Scrape run skipped because another process holds the lease. owner=%s expires_at=%s expires_in_seconds=%s',
                lease.get('owner') or 'unknown',
                lease.get('expires_at') or 'unknown',
                lease.get('expires_in_seconds'),
            )
            return summary.as_dict()

        renewal = start_lease_renewal(lease_owner, lease_seconds)
        logger.info('Starting scrape run...')
        run_id = start_scraper_run()

        try:
            sources = active_sources()
        except Exception:
            logger.exception('Could not load scraping sources.')
            finish_scraper_run(run_id, 'failed', summary.as_dict(), 'could_not_load_sources')
            return summary.as_dict()

        for source in sources:
            summary.sources += 1
            list_url = source['list_url']
            custom_headers, header_controls = parse_custom_headers(source)
            request_policy = build_request_policy(list_url, header_controls)
            try:
                validate_url_for_request(normalize_url_for_request(list_url), request_policy)
                if source.get('is_api') == 1:
                    logger.info('Starting API source: %s (%s)', source.get('name'), sanitize_url_for_log(list_url))
                    process_api_source(source, list_url, custom_headers, request_policy, summary, is_first_run)
                else:
                    logger.info('Starting HTML source: %s (%s)', source.get('name'), sanitize_url_for_log(list_url))
                    process_html_source(source, list_url, custom_headers, request_policy, summary, is_first_run)
            except URLBlockedError as exc:
                summary.rejected += 1
                logger.warning('Rejected source %s: %s', source.get('name'), exc)
            except Exception:
                summary.rejected += 1
                logger.exception('Source failed: %s', source.get('name'))

        summary_payload = summary.as_dict()
        logger.info('Scrape run completed. Summary: %s', summary_payload)
        finish_scraper_run(run_id, 'success', summary_payload)
        return summary_payload
    except Exception as exc:
        if run_id:
            finish_scraper_run(run_id, 'failed', summary.as_dict(), exc)
        raise
    finally:
        if renewal:
            stop_event, thread = renewal
            stop_event.set()
            thread.join(timeout=1)
        release_scrape_lease(lease_owner)
        _RUN_LOCK.release()
