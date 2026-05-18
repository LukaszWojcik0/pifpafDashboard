from apscheduler.schedulers.blocking import BlockingScheduler
import os
import logging
from scraper import run_scraper

logger = logging.getLogger(__name__)

def start_scheduler():
    interval_minutes = int(os.getenv('SCRAPE_INTERVAL_MINUTES', 10))
    scheduler = BlockingScheduler()
    
    # Run once immediately
    logger.info("Running initial scrape...")
    alert_on_first = os.getenv('ALERT_ON_FIRST_RUN', 'false').lower() == 'true'
    run_scraper(is_first_run=not alert_on_first)
    
    # Schedule subsequent runs
    scheduler.add_job(
        lambda: run_scraper(is_first_run=False), 
        'interval', 
        minutes=interval_minutes
    )
    
    logger.info(f"Scheduler started. Next run in {interval_minutes} minutes.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")
