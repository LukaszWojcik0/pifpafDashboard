import email.utils
import ipaddress
import logging
import socket
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 10
DEFAULT_MAX_REDIRECTS = 3
DEFAULT_MAX_RETRY_AFTER_SECONDS = 30
DEFAULT_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'

CONTROL_KEYS = {
    '__allow_http',
    '__allow_http_origins',
    '__allowed_origins',
    '__credential_origins',
}
SENSITIVE_HEADER_NAMES = {
    'authorization',
    'cookie',
    'proxy-authorization',
    'x-api-key',
    'x-auth-token',
    'x-access-token',
    'api-key',
}
SENSITIVE_HEADER_PARTS = ('token', 'secret', 'password', 'passwd', 'apikey', 'api-key', 'authorization', 'cookie')
SENSITIVE_QUERY_PARTS = ('token', 'secret', 'password', 'passwd', 'apikey', 'api_key', 'key', 'auth', 'signature')
METADATA_IPS = {
    ipaddress.ip_address('169.254.169.254'),
    ipaddress.ip_address('100.100.100.200'),
}


class URLBlockedError(ValueError):
    pass


@dataclass
class RequestPolicy:
    credential_origins: set[str] = field(default_factory=set)
    allow_http_origins: set[str] = field(default_factory=set)
    max_redirects: int = DEFAULT_MAX_REDIRECTS
    max_retry_after_seconds: int = DEFAULT_MAX_RETRY_AFTER_SECONDS

    def allows_http(self, url):
        return origin_for_url(url) in self.allow_http_origins

    def allows_credentials(self, url):
        return origin_for_url(url) in self.credential_origins


def origin_for_url(url):
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or '').lower()
    port = parsed.port
    if port is None:
        port = 443 if scheme == 'https' else 80
    return f'{scheme}://{host}:{port}'


def normalize_url_for_request(url, base_url=None):
    joined = urljoin(base_url, (url or '').strip()) if base_url else (url or '').strip()
    parsed = urlparse(joined)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or '/'
    return urlunparse((scheme, netloc, path, '', parsed.query, ''))


def sanitize_url_for_log(url):
    parsed = urlparse(url or '')
    netloc = parsed.hostname or ''
    if parsed.port:
        netloc = f'{netloc}:{parsed.port}'
    safe_query = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if any(part in key.lower() for part in SENSITIVE_QUERY_PARTS):
            safe_query.append((key, '***'))
        else:
            safe_query.append((key, value))
    return urlunparse((parsed.scheme, netloc, parsed.path, '', urlencode(safe_query), ''))


def mask_header_value(name, value):
    if is_sensitive_header(name):
        return '***'
    return value


def is_sensitive_header(name):
    lowered = name.lower()
    return lowered in SENSITIVE_HEADER_NAMES or any(part in lowered for part in SENSITIVE_HEADER_PARTS)


def split_header_controls(raw_headers):
    headers = {}
    controls = {}
    for key, value in (raw_headers or {}).items():
        if key in CONTROL_KEYS:
            controls[key] = value
        else:
            headers[key] = value
    return headers, controls


def _as_origin_set(values):
    if not values:
        return set()
    if isinstance(values, str):
        values = [values]
    origins = set()
    for value in values:
        try:
            origins.add(origin_for_url(normalize_url_for_request(value)))
        except Exception:
            logger.warning('Ignoring invalid configured origin: %s', sanitize_url_for_log(str(value)))
    return origins


def build_request_policy(source_url, controls=None):
    source_origin = origin_for_url(normalize_url_for_request(source_url))
    controls = controls or {}
    credential_origins = {source_origin}
    credential_origins.update(_as_origin_set(controls.get('__allowed_origins')))
    credential_origins.update(_as_origin_set(controls.get('__credential_origins')))

    allow_http_origins = set()
    if controls.get('__allow_http') is True:
        allow_http_origins.add(source_origin)
    allow_http_origins.update(_as_origin_set(controls.get('__allow_http_origins')))

    return RequestPolicy(
        credential_origins=credential_origins,
        allow_http_origins=allow_http_origins,
    )


def _ip_is_blocked(ip):
    return (
        ip in METADATA_IPS
        or ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_reserved
        or not ip.is_global
    )


def resolve_host_ips(hostname, port):
    try:
        literal = ipaddress.ip_address(hostname.strip('[]'))
        return [literal]
    except ValueError:
        pass

    try:
        addrinfos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise URLBlockedError(f'DNS resolution failed: {exc}') from exc

    addresses = []
    for info in addrinfos:
        sockaddr = info[4]
        ip_text = sockaddr[0]
        try:
            addresses.append(ipaddress.ip_address(ip_text))
        except ValueError as exc:
            raise URLBlockedError(f'Invalid resolved IP address: {ip_text}') from exc

    if not addresses:
        raise URLBlockedError('DNS resolution returned no addresses')
    return addresses


def validate_url_for_request(url, policy=None):
    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'}:
        raise URLBlockedError('Only http/https URLs are supported')
    if parsed.scheme != 'https' and not (policy and policy.allows_http(url)):
        raise URLBlockedError('HTTP URL is not allowed for this source')
    if parsed.username or parsed.password:
        raise URLBlockedError('URL credentials are not allowed')
    if not parsed.hostname:
        raise URLBlockedError('URL hostname is required')

    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme == 'https' else 80

    addresses = resolve_host_ips(parsed.hostname, port)
    blocked = [str(ip) for ip in addresses if _ip_is_blocked(ip)]
    if blocked:
        raise URLBlockedError(f'Blocked non-public resolved address: {", ".join(blocked)}')
    return True


def headers_for_url(custom_headers, url, policy=None):
    headers = {'User-Agent': DEFAULT_USER_AGENT}
    for name, value in (custom_headers or {}).items():
        if is_sensitive_header(name) and policy and not policy.allows_credentials(url):
            continue
        headers[name] = value
    return headers


def parse_retry_after(value):
    if not value:
        return None
    try:
        return max(0, int(value))
    except ValueError:
        pass
    try:
        parsed_date = email.utils.parsedate_to_datetime(value)
        if parsed_date.tzinfo is None:
            parsed_date = parsed_date.replace(tzinfo=timezone.utc)
        return max(0, int((parsed_date - datetime.now(timezone.utc)).total_seconds()))
    except Exception:
        return None


def should_retry_response(response):
    return response.status_code == 429 or 500 <= response.status_code < 600


def safe_get(
    url,
    *,
    retries=3,
    backoff_factor=1,
    custom_headers=None,
    policy=None,
    timeout=DEFAULT_TIMEOUT_SECONDS,
    sleep=time.sleep,
):
    current_url = normalize_url_for_request(url)
    redirects_remaining = policy.max_redirects if policy else DEFAULT_MAX_REDIRECTS

    for attempt in range(retries):
        try:
            validate_url_for_request(current_url, policy)
        except URLBlockedError as exc:
            logger.warning('Blocked request to %s: %s', sanitize_url_for_log(current_url), exc)
            return None

        try:
            response = requests.get(
                current_url,
                headers=headers_for_url(custom_headers, current_url, policy),
                timeout=timeout,
                allow_redirects=False,
            )
        except requests.exceptions.Timeout as exc:
            logger.warning('Timeout fetching %s on attempt %s/%s: %s', sanitize_url_for_log(current_url), attempt + 1, retries, exc)
            if attempt < retries - 1:
                sleep(backoff_factor * (2 ** attempt))
            continue
        except requests.exceptions.RequestException as exc:
            logger.warning('Request failed for %s on attempt %s/%s: %s', sanitize_url_for_log(current_url), attempt + 1, retries, exc)
            if attempt < retries - 1:
                sleep(backoff_factor * (2 ** attempt))
            continue

        if 300 <= response.status_code < 400:
            location = response.headers.get('Location')
            if not location:
                logger.warning('Redirect from %s without Location header', sanitize_url_for_log(current_url))
                return None
            if redirects_remaining <= 0:
                logger.warning('Redirect limit exceeded for %s', sanitize_url_for_log(current_url))
                return None
            next_url = normalize_url_for_request(location, current_url)
            try:
                validate_url_for_request(next_url, policy)
            except URLBlockedError as exc:
                logger.warning('Blocked redirect from %s to %s: %s', sanitize_url_for_log(current_url), sanitize_url_for_log(next_url), exc)
                return None
            current_url = next_url
            redirects_remaining -= 1
            continue

        if response.status_code >= 400:
            logger.warning('HTTP %s while fetching %s', response.status_code, sanitize_url_for_log(current_url))
            if should_retry_response(response) and attempt < retries - 1:
                retry_after = parse_retry_after(response.headers.get('Retry-After'))
                if retry_after is not None:
                    retry_after = min(retry_after, policy.max_retry_after_seconds if policy else DEFAULT_MAX_RETRY_AFTER_SECONDS)
                    sleep(retry_after)
                else:
                    sleep(backoff_factor * (2 ** attempt))
                continue
            return None

        return response.text

    logger.error('Failed to fetch %s after %s retries.', sanitize_url_for_log(current_url), retries)
    return None
