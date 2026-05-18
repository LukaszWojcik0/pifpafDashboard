import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def send_ntfy_alert(ntfy_url: str, title: str, event_title: str, event_date: str, event_time: str, prev_avail: Optional[int], curr_avail: Optional[int], url: str):
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
        logger.error(f"Błąd wysyłania powiadomienia ntfy: {e}")
