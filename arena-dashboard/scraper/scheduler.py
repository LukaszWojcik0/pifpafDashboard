import logging
import os
from datetime import datetime, timedelta

from apscheduler.schedulers.blocking import BlockingScheduler

from db import update_status
from scraper import run_scraper

logger = logging.getLogger(__name__)


def run_and_schedule(is_first_run, interval_minutes):
    try:
        run_scraper(is_first_run=is_first_run)
    except Exception:
        logger.exception('Scrape run failed, scheduler will continue.')
    finally:
        next_time = datetime.now() + timedelta(minutes=interval_minutes)
        update_status('next_scrape_time', next_time.isoformat())


def start_scheduler():
    interval_minutes = int(os.getenv('SCRAPE_INTERVAL_MINUTES', 10))
    scheduler = BlockingScheduler()

    logger.info('Running initial scrape...')
    alert_on_first = os.getenv('ALERT_ON_FIRST_RUN', 'false').lower() == 'true'
    run_and_schedule(is_first_run=not alert_on_first, interval_minutes=interval_minutes)

    scheduler.add_job(
        lambda: run_and_schedule(is_first_run=False, interval_minutes=interval_minutes),
        'interval',
        minutes=interval_minutes,
    )

    logger.info('Scheduler started. Next run in %s minutes.', interval_minutes)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info('Scheduler stopped.')
