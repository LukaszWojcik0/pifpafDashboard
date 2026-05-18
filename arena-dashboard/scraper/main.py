import logging
import os
from dotenv import load_dotenv
from db import init_db
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
    init_db()
    start_scheduler()

if __name__ == "__main__":
    main()
