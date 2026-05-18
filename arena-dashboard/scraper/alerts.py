import os
import requests
import logging

logger = logging.getLogger(__name__)

NTFY_URL = os.getenv('NTFY_URL')

def send_alert(title, message, tags=None):
    if not NTFY_URL:
        return
        
    headers = {}
    if tags:
        headers["Tags"] = ",".join(tags)
    headers["Title"] = title

    try:
        response = requests.post(
            NTFY_URL,
            data=message.encode(encoding='utf-8'),
            headers=headers,
            timeout=5
        )
        response.raise_for_status()
        logger.info(f"Alert sent successfully: {title}")
    except Exception as e:
        logger.error(f"Failed to send alert: {e}")
