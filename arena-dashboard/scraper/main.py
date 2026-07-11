import logging
import os
import time
from dotenv import load_dotenv
from db import SchemaMigrationRequired, init_db
from scheduler import start_scheduler

# Load environment variables if .env exists (useful for local testing)
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting arena-dashboard scraper service...")
    try:
        init_db()
    except SchemaMigrationRequired as exc:
        logger.error("%s", exc)
        logger.error("Scraper scheduler will not start until the controlled SQLite migration is completed.")
        while True:
            time.sleep(3600)
    start_scheduler()

if __name__ == "__main__":
    main()
