import os
import requests
import logging

logger = logging.getLogger(__name__)

NTFY_URL = os.getenv('NTFY_URL')

def send_alert(title, message, tags=None, priority=None, click=None, url=None):
    target_url = url or NTFY_URL
    if not target_url:
        return
        
    headers = {}
    if tags:
        headers["Tags"] = ",".join(tags)
    headers["Title"] = title
    if priority:
        headers["Priority"] = str(priority)
    if click:
        headers["Click"] = click

    try:
        response = requests.post(
            target_url,
            data=message.encode(encoding='utf-8'),
            headers=headers,
            timeout=5
        )
        response.raise_for_status()
        logger.info(f"Alert sent successfully: {title}")
    except Exception as e:
        logger.error(f"Failed to send alert: {e}")
