import logging
import sqlite3
import traceback
from datetime import datetime

from db import init_db, upsert_event, save_snapshot, get_db_path
from scraper import scrape_arena_events
from scheduler import start_scheduler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_scraper_job(is_first_run: bool = False):
    logger.info("--- Rozpoczęcie sprawdzania wydarzeń ---")
    start_time = datetime.now()
    try:
        results = scrape_arena_events()
        logger.info(f"Odebrano dane dla {len(results)} wydarzeń.")
        
        with sqlite3.connect(get_db_path()) as conn:
            # Upewniamy się, że tryb to autocommit/WAL
            for event in results:
                try:
                    event_id = upsert_event(conn, event, is_first_run)
                    save_snapshot(conn, event_id, event.get("tickets_available"))
                except Exception as db_err:
                    logger.error(f"Błąd podczas zapisu wydarzenia {event.get('url')}: {db_err}")
    except Exception as e:
        logger.error(f"Wystąpił błąd podczas działania scrapera: {e}")
        logger.debug(traceback.format_exc())
    finally:
        end_time = datetime.now()
        logger.info(f"--- Zakończenie sprawdzania (Czas trwania: {end_time - start_time}) ---")

if __name__ == "__main__":
    init_db()
    
    # Pierwsze uruchomienie przy starcie kontenera (z cichym importem jeśli bazy wcześniej nie było)
    run_scraper_job(is_first_run=True)
    
    # Przejście w tryb cykliczny
    start_scheduler(run_scraper_job)
