from apscheduler.schedulers.blocking import BlockingScheduler
import os
import logging
from datetime import datetime, timedelta
from scraper import run_scraper
from db import update_status

logger = logging.getLogger(__name__)

def run_and_schedule(is_first_run, interval_minutes):
    run_scraper(is_first_run=is_first_run)
    next_time = datetime.now() + timedelta(minutes=interval_minutes)
    update_status('next_scrape_time', next_time.isoformat())

def start_scheduler():
    interval_minutes = int(os.getenv('SCRAPE_INTERVAL_MINUTES', 10))
    scheduler = BlockingScheduler()
    
    # Run once immediately
    logger.info("Running initial scrape...")
    alert_on_first = os.getenv('ALERT_ON_FIRST_RUN', 'false').lower() == 'true'
    run_and_schedule(is_first_run=not alert_on_first, interval_minutes=interval_minutes)
    
    # Schedule subsequent runs
    scheduler.add_job(
        lambda: run_and_schedule(is_first_run=False, interval_minutes=interval_minutes), 
        'interval', 
        minutes=interval_minutes
    )
    
    logger.info(f"Scheduler started. Next run in {interval_minutes} minutes.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")
