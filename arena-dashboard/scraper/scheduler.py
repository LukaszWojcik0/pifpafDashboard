import os
import logging
from apscheduler.schedulers.blocking import BlockingScheduler

def start_scheduler(job_function):
    logger = logging.getLogger(__name__)
    
    try:
        interval_minutes = int(os.environ.get("SCRAPE_INTERVAL_MINUTES", 10))
    except ValueError:
        logger.warning("Nieprawidłowa wartość zmiennej SCRAPE_INTERVAL_MINUTES, używam domyślnej: 10 minut.")
        interval_minutes = 10

    scheduler = BlockingScheduler()
    scheduler.add_job(lambda: job_function(is_first_run=False), 'interval', minutes=interval_minutes)
    
    logger.info(f"Uruchomiono scheduler. Interwał: {interval_minutes} minut.")
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Zatrzymano scheduler.")
