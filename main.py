"""
main.py — MENA Venture Intelligence Dashboard
Pipeline entrypoint: runs once immediately, then on a recurring schedule.

Usage:
    python main.py              # Scheduled mode (default)
    python main.py --once       # Run pipeline once and exit
"""

import argparse
import os
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

# ── Logging setup ─────────────────────────────────────────────────────────────
LOG_DIR = os.getenv("LOG_DIR", "logs")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
os.makedirs(LOG_DIR, exist_ok=True)

logger.remove()
logger.add(sys.stderr, level=LOG_LEVEL, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | {message}")
logger.add(
    f"{LOG_DIR}/pipeline_{{time:YYYY-MM-DD}}.log",
    rotation="1 week",
    retention="4 weeks",
    level=LOG_LEVEL,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{line} | {message}",
    enqueue=True,
)


def run_pipeline() -> None:
    """Import and execute the full scraping + extraction pipeline."""
    from src.scraper.pipeline import run_full_pipeline

    logger.info("═" * 60)
    logger.info("Pipeline run starting")
    try:
        stats = run_full_pipeline()
        logger.info(
            f"Pipeline complete — "
            f"articles_fetched={stats['articles_fetched']} | "
            f"rounds_inserted={stats['rounds_inserted']} | "
            f"skipped_duplicates={stats['skipped_duplicates']} | "
            f"low_confidence_flagged={stats['low_confidence_flagged']}"
        )
    except Exception as exc:
        logger.exception(f"Pipeline run failed: {exc}")
    logger.info("═" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="MENA Venture Intelligence Pipeline")
    parser.add_argument("--once", action="store_true", help="Run pipeline once and exit")
    args = parser.parse_args()

    if args.once:
        run_pipeline()
        return

    interval_hours = int(os.getenv("PIPELINE_SCHEDULE_HOURS", "12"))
    logger.info(f"Scheduler starting — pipeline will run every {interval_hours}h")

    # Run immediately on boot, then on schedule
    run_pipeline()

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(run_pipeline, "interval", hours=interval_hours, id="pipeline")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    main()
