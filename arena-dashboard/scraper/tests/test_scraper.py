import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

SCRAPER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRAPER_DIR))

import db  # noqa: E402
import request_security  # noqa: E402
import scraper  # noqa: E402


FIXTURES = Path(__file__).resolve().parent / 'fixtures'
PUBLIC_IP = request_security.ipaddress.ip_address('93.184.216.34')


def fixture(name):
    return (FIXTURES / name).read_text(encoding='utf-8')


def source(**overrides):
    data = {
        'id': 1,
        'name': 'Arena Walki',
        'list_url': 'https://arenawalki.pl/gry-otwarte/',
        'list_links_selector': 'a[href*="/produkt/"], a[href*="/wydarzenie/"]',
        'title_selector': 'h1',
        'date_selector': '[class*="date"], [class*="data"]',
        'time_selector': '[class*="time"], [class*="czas"], [class*="godzina"]',
        'image_selector': 'meta[property="og:image"], .wp-post-image, .woocommerce-product-gallery__image img',
        'tickets_regex': r'\((\d+)\s+dost(?:epnych|Ä™pnych|Ă„â„˘pnych)\)|(\d+)\s+dost(?:epnych|Ä™pnych|Ă„â„˘pnych)',
        'sold_out_regex': r'wyprzedane|brak biletow|brak biletĂłw|brak w magazynie|sprzedaz zamknieta|sprzedaĹĽ zamkniÄ™ta',
        'is_active': 1,
        'is_api': 0,
        'request_headers': None,
        'ntfy_url': None,
        'ntfy_template': None,
    }
    data.update(overrides)
    return data


class TempDbTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.old_db_path = db.DB_PATH
        db.DB_PATH = os.path.join(self.tmpdir.name, 'test.db')
        db.init_db()
        self.addCleanup(self.cleanup_db)

    def cleanup_db(self):
        db.DB_PATH = self.old_db_path
        self.tmpdir.cleanup()

    def rows(self, sql):
        conn = sqlite3.connect(db.DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            return [dict(row) for row in conn.execute(sql).fetchall()]
        finally:
            conn.close()

    def replace_sources(self, sources):
        conn = sqlite3.connect(db.DB_PATH)
        try:
            conn.execute('DELETE FROM scraping_sources')
            for item in sources:
                conn.execute(
                    '''
                    INSERT INTO scraping_sources
                    (name, list_url, list_links_selector, title_selector, date_selector, time_selector,
                     image_selector, tickets_regex, sold_out_regex, is_active, is_api, request_headers,
                     ntfy_url, ntfy_template)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        item['name'], item['list_url'], item['list_links_selector'], item['title_selector'],
                        item['date_selector'], item['time_selector'], item['image_selector'],
                        item['tickets_regex'], item['sold_out_regex'], item['is_active'], item['is_api'],
                        item['request_headers'], item['ntfy_url'], item['ntfy_template'],
                    ),
                )
            conn.commit()
        finally:
            conn.close()


class EventUrlTests(unittest.TestCase):
    def test_detects_events_path_with_legacy_selector_and_deduplicates(self):
        urls = scraper.get_event_urls(
            fixture('current_list.html'),
            'https://arenawalki.pl/gry-otwarte/',
            'a[href*="/produkt/"], a[href*="/wydarzenie/"]',
        )
        self.assertIn('https://arenawalki.pl/events/arena-open-alpha', urls)
        self.assertIn('https://arenawalki.pl/wydarzenie/stary-format', urls)
        self.assertEqual(urls.count('https://arenawalki.pl/events/arena-open-alpha'), 1)
        self.assertNotIn('https://arenawalki.pl/kontakt', urls)

    def test_no_events_page_returns_no_urls(self):
        urls = scraper.get_event_urls(fixture('no_events.html'), 'https://arenawalki.pl/gry-otwarte/', None)
        self.assertEqual(urls, [])

    def test_multiple_events_are_normalized_and_deduplicated(self):
        urls = scraper.get_event_urls(fixture('multiple_events.html'), 'https://arenawalki.pl/gry-otwarte/', None)
        self.assertEqual(
            urls,
            [
                'https://arenawalki.pl/events/alpha',
                'https://arenawalki.pl/events/beta',
                'https://arenawalki.pl/produkt/legacy',
            ],
        )


class ParserTests(unittest.TestCase):
    def test_one_event_fixture_parses_known_ten(self):
        data = scraper.scrape_event_details(fixture('one_event.html'), 'https://arenawalki.pl/events/alpha', source())
        self.assertTrue(data['measurement_known'])
        self.assertEqual(data['tickets_available'], 10)

    def test_missing_elements_are_unknown_not_zero(self):
        data = scraper.scrape_event_details(fixture('missing_elements.html'), 'https://arenawalki.pl/events/missing', source())
        self.assertFalse(data['measurement_known'])
        self.assertIsNone(data['tickets_available'])
        self.assertEqual(data['rejection_reason'], 'tickets_not_found')

    def test_changed_classes_can_still_parse_zero(self):
        data = scraper.scrape_event_details(fixture('changed_classes.html'), 'https://arenawalki.pl/events/changed', source())
        self.assertTrue(data['measurement_known'])
        self.assertEqual(data['tickets_available'], 0)

    def test_invalid_regex_is_caught(self):
        data = scraper.scrape_event_details(
            fixture('one_event.html'),
            'https://arenawalki.pl/events/alpha',
            source(tickets_regex='('),
        )
        self.assertFalse(data['measurement_known'])
        self.assertIn('invalid tickets_regex', data['rejection_reason'])

    def test_invalid_css_selector_is_caught(self):
        urls = scraper.get_event_urls(fixture('current_list.html'), 'https://arenawalki.pl/gry-otwarte/', 'a[')
        self.assertIn('https://arenawalki.pl/events/arena-open-alpha', urls)
        data = scraper.scrape_event_details(
            fixture('one_event.html'),
            'https://arenawalki.pl/events/alpha',
            source(title_selector='h1['),
        )
        self.assertEqual(data['tickets_available'], 10)

    def test_antibot_html_200_is_unknown(self):
        data = scraper.scrape_event_details(fixture('antibot_200.html'), 'https://arenawalki.pl/events/blocked', source())
        self.assertFalse(data['measurement_known'])
        self.assertEqual(data['rejection_reason'], 'antibot_page')

    def test_incomplete_html_is_parsed(self):
        data = scraper.scrape_event_details(fixture('incomplete.html'), 'https://arenawalki.pl/events/incomplete', source())
        self.assertTrue(data['measurement_known'])
        self.assertEqual(data['tickets_available'], 7)


class DbUnknownTests(TempDbTest):
    def test_ten_unknown_ten_keeps_last_valid_and_skips_unknown_snapshot(self):
        db.update_event('event-1', 'Alpha', 'https://example.test/a', 'date', 10)
        db.update_event('event-1', 'Alpha', 'https://example.test/a', 'date', None)
        db.update_event('event-1', 'Alpha', 'https://example.test/a', 'date', 10)
        events = self.rows('SELECT max_available FROM events WHERE id = "event-1"')
        snapshots = self.rows('SELECT available, status FROM snapshots WHERE event_id = "event-1" ORDER BY id')
        self.assertEqual(events[0]['max_available'], 10)
        self.assertEqual([row['available'] for row in snapshots], [10])
        self.assertEqual([row['status'] for row in snapshots], ['available'])

    def test_ten_then_valid_zero_writes_zero_snapshot(self):
        db.update_event('event-1', 'Alpha', 'https://example.test/a', 'date', 10)
        db.update_event('event-1', 'Alpha', 'https://example.test/a', 'date', 0)
        events = self.rows('SELECT max_available FROM events WHERE id = "event-1"')
        snapshots = self.rows('SELECT available, status FROM snapshots WHERE event_id = "event-1" ORDER BY id')
        self.assertEqual(events[0]['max_available'], 10)
        self.assertEqual([row['available'] for row in snapshots], [10, 0])
        self.assertEqual([row['status'] for row in snapshots], ['available', 'sold_out'])


class FetchTests(unittest.TestCase):
    def test_timeout_returns_none(self):
        with patch('request_security.resolve_host_ips', return_value=[PUBLIC_IP]):
            with patch('request_security.requests.get', side_effect=requests.exceptions.Timeout('slow')):
                self.assertIsNone(scraper.get_page_with_retry('https://example.test/events/slow', retries=1))

    def test_http_error_statuses_return_none(self):
        class Response:
            def __init__(self, status_code):
                self.status_code = status_code
                self.text = 'error'
                self.headers = {}

        for status in [404, 429, 500]:
            with self.subTest(status=status):
                with patch('request_security.resolve_host_ips', return_value=[PUBLIC_IP]):
                    with patch('request_security.requests.get', return_value=Response(status)):
                        self.assertIsNone(scraper.get_page_with_retry(f'https://example.test/{status}', retries=1))


class SecurityValidationTests(unittest.TestCase):
    def assert_blocked(self, url):
        with self.assertRaises(request_security.URLBlockedError):
            request_security.validate_url_for_request(url, request_security.build_request_policy('https://example.test'))

    def test_blocks_loopback_localhost_private_metadata_and_ipv6(self):
        self.assert_blocked('https://127.0.0.1/events/a')
        self.assert_blocked('https://10.0.0.5/events/a')
        self.assert_blocked('https://172.16.1.5/events/a')
        self.assert_blocked('https://192.168.1.5/events/a')
        self.assert_blocked('https://169.254.169.254/latest/meta-data/')
        self.assert_blocked('https://[::1]/events/a')
        self.assert_blocked('https://[fd00::1]/events/a')
        with patch('request_security.socket.getaddrinfo', return_value=[(None, None, None, None, ('127.0.0.1', 443))]):
            self.assert_blocked('https://localhost/events/a')

    def test_blocks_public_hostname_resolving_to_private_ip(self):
        with patch('request_security.socket.getaddrinfo', return_value=[(None, None, None, None, ('10.0.0.10', 443))]):
            self.assert_blocked('https://public.example.test/events/a')

    def test_blocks_redirect_to_private_ip(self):
        class Response:
            status_code = 302
            text = ''
            headers = {'Location': 'https://10.0.0.1/events/private'}

        with patch('request_security.socket.getaddrinfo', return_value=[(None, None, None, None, (str(PUBLIC_IP), 443))]):
            with patch('request_security.requests.get', return_value=Response()) as get_mock:
                result = request_security.safe_get('https://example.test/events/start')
        self.assertIsNone(result)
        self.assertEqual(get_mock.call_count, 1)

    def test_redirect_to_other_origin_does_not_forward_authorization(self):
        calls = []

        class Response:
            def __init__(self, status_code, headers=None, text='ok'):
                self.status_code = status_code
                self.headers = headers or {}
                self.text = text

        def fake_get(url, headers=None, **kwargs):
            calls.append((url, headers or {}))
            if len(calls) == 1:
                return Response(302, {'Location': 'https://other.example.test/events/a'})
            return Response(200, text='done')

        policy = request_security.build_request_policy('https://source.example.test')
        with patch('request_security.resolve_host_ips', return_value=[PUBLIC_IP]):
            with patch('request_security.requests.get', side_effect=fake_get):
                result = request_security.safe_get(
                    'https://source.example.test/events/start',
                    custom_headers={'Authorization': 'Bearer secret'},
                    policy=policy,
                )

        self.assertEqual(result, 'done')
        self.assertIn('Authorization', calls[0][1])
        self.assertNotIn('Authorization', calls[1][1])

    def test_authorization_is_not_sent_to_unapproved_origin(self):
        captured_headers = {}

        class Response:
            status_code = 200
            text = 'ok'
            headers = {}

        def fake_get(url, headers=None, **kwargs):
            captured_headers.update(headers or {})
            return Response()

        policy = request_security.build_request_policy('https://source.example.test')
        with patch('request_security.resolve_host_ips', return_value=[PUBLIC_IP]):
            with patch('request_security.requests.get', side_effect=fake_get):
                result = request_security.safe_get(
                    'https://other.example.test/events/a',
                    custom_headers={'Authorization': 'Bearer secret', 'Accept': 'text/html'},
                    policy=policy,
                )

        self.assertEqual(result, 'ok')
        self.assertNotIn('Authorization', captured_headers)
        self.assertEqual(captured_headers['Accept'], 'text/html')


class RunScraperTests(TempDbTest):
    def test_one_bad_event_does_not_block_good_event(self):
        self.replace_sources([source()])
        pages = {
            'https://arenawalki.pl/gry-otwarte': fixture('multiple_events.html'),
            'https://arenawalki.pl/events/alpha': fixture('one_event.html'),
            'https://arenawalki.pl/events/beta': None,
            'https://arenawalki.pl/produkt/legacy': fixture('missing_elements.html'),
        }

        def fake_fetch(url, **kwargs):
            return pages.get(scraper.normalize_url(url, url))

        with patch('scraper.validate_url_for_request', return_value=True):
            with patch('scraper.safe_get', side_effect=fake_fetch), patch('scraper.time.sleep'):
                summary = scraper.run_scraper(is_first_run=True)

        self.assertEqual(summary['found'], 3)
        self.assertEqual(summary['valid'], 1)
        self.assertEqual(summary['rejected'], 2)
        self.assertEqual(summary['created'], 2)
        self.assertEqual(len(self.rows('SELECT * FROM snapshots')), 1)

    def test_reprocessing_same_event_updates_instead_of_duplicating_event(self):
        self.replace_sources([source()])
        pages = {
            'https://arenawalki.pl/gry-otwarte': '<a href="/events/alpha">Alpha</a><a href="/events/alpha?utm_source=x#dup">Alpha duplicate</a>',
            'https://arenawalki.pl/events/alpha': fixture('one_event.html'),
        }

        def fake_fetch(url, **kwargs):
            return pages.get(scraper.normalize_url(url, url))

        with patch('scraper.validate_url_for_request', return_value=True):
            with patch('scraper.safe_get', side_effect=fake_fetch), patch('scraper.time.sleep'):
                first = scraper.run_scraper(is_first_run=True)
                second = scraper.run_scraper(is_first_run=True)

        self.assertEqual(first['found'], 1)
        self.assertEqual(second['found'], 1)
        self.assertEqual(len(self.rows('SELECT * FROM events')), 1)
        self.assertEqual(len(self.rows('SELECT * FROM snapshots')), 1)
        self.assertEqual(second['updated'], 1)

    def test_antibot_list_with_http_200_is_rejected(self):
        self.replace_sources([source()])

        def fake_fetch(url, **kwargs):
            return fixture('antibot_200.html')

        with patch('scraper.validate_url_for_request', return_value=True):
            with patch('scraper.safe_get', side_effect=fake_fetch), patch('scraper.time.sleep'):
                summary = scraper.run_scraper(is_first_run=True)

        self.assertEqual(summary['found'], 0)
        self.assertEqual(summary['rejected'], 1)
        self.assertEqual(len(self.rows('SELECT * FROM snapshots')), 0)

    def test_malicious_html_url_is_not_requested_or_saved(self):
        self.replace_sources([source()])

        class Response:
            status_code = 200
            text = '<a href="https://127.0.0.1/events/private">bad</a>'
            headers = {}

        with patch('request_security.socket.getaddrinfo', return_value=[(None, None, None, None, (str(PUBLIC_IP), 443))]):
            with patch('request_security.requests.get', return_value=Response()) as get_mock:
                summary = scraper.run_scraper(is_first_run=True)

        self.assertEqual(summary['found'], 1)
        self.assertEqual(summary['rejected'], 1)
        self.assertEqual(get_mock.call_count, 1)
        self.assertEqual(len(self.rows('SELECT * FROM events')), 0)

    def test_malicious_json_url_is_rejected(self):
        self.replace_sources([
            source(
                name='API',
                list_url='https://api.example.test/events',
                list_links_selector='content',
                title_selector='name',
                sold_out_regex='id',
                is_api=1,
            )
        ])

        class Response:
            status_code = 200
            text = '{"content":[{"name":"Bad","id":"https://127.0.0.1/events/private"}]}'
            headers = {}

        with patch('request_security.socket.getaddrinfo', return_value=[(None, None, None, None, (str(PUBLIC_IP), 443))]):
            with patch('request_security.requests.get', return_value=Response()):
                summary = scraper.run_scraper(is_first_run=True)

        self.assertEqual(summary['found'], 1)
        self.assertEqual(summary['rejected'], 1)
        self.assertEqual(len(self.rows('SELECT * FROM events')), 0)

    def test_two_parallel_runs_do_not_overlap_in_one_process(self):
        self.replace_sources([source()])
        active_started = threading.Event()
        release_active = threading.Event()

        def slow_active_sources():
            active_started.set()
            release_active.wait(timeout=2)
            return []

        results = []
        with patch('scraper.active_sources', side_effect=slow_active_sources):
            first = threading.Thread(target=lambda: results.append(scraper.run_scraper(is_first_run=True)))
            first.start()
            active_started.wait(timeout=2)
            second = scraper.run_scraper(is_first_run=True)
            release_active.set()
            first.join(timeout=2)

        self.assertTrue(second['skipped'])
        self.assertFalse(results[0]['skipped'])

    def test_expired_lease_can_be_acquired_after_simulated_crash(self):
        conn = sqlite3.connect(db.DB_PATH)
        try:
            conn.execute("INSERT INTO system_status (key, value) VALUES ('scrape_lock_owner', 'dead')")
            conn.execute("INSERT INTO system_status (key, value) VALUES ('scrape_lock_expires_at', '2000-01-01T00:00:00')")
            conn.commit()
        finally:
            conn.close()

        self.assertTrue(db.acquire_scrape_lease('new-owner', ttl_seconds=60))
        db.release_scrape_lease('new-owner')


if __name__ == '__main__':
    unittest.main()
