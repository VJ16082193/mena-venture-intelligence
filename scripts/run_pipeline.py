"""
scripts/run_pipeline.py — Manually trigger a single pipeline run.

Usage:
    python scripts/run_pipeline.py
    python scripts/run_pipeline.py --source menabytes   # Single source only
    python scripts/run_pipeline.py --dry-run            # Scrape but don't write to DB
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from loguru import logger

load_dotenv()

logger.remove()
logger.add(sys.stderr, level="DEBUG", format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}")


def main():
    parser = argparse.ArgumentParser(description="Run MENA VC scraping pipeline manually")
    parser.add_argument(
        "--source",
        choices=["menabytes", "wamda", "arabnet"],
        default=None,
        help="Run a single source only (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape and extract but do not write to the database",
    )
    args = parser.parse_args()

    if args.dry_run:
        logger.info("DRY RUN MODE — no data will be written to the database")

    if args.source:
        _run_single_source(args.source, args.dry_run)
    else:
        _run_all(args.dry_run)


def _run_all(dry_run: bool):
    from src.scraper.pipeline import run_full_pipeline
    from src.database.connection import health_check

    if not dry_run:
        if not health_check():
            logger.error("Cannot connect to database. Check DATABASE_URL.")
            sys.exit(1)

    if dry_run:
        from src.scraper.menabytes import MENABytesScraper
        from src.scraper.wamda import WamdaScraper
        from src.scraper.arabnet import ArabNetScraper
        from src.scraper.currency import ensure_rates_loaded
        ensure_rates_loaded()
        for scraper in [MENABytesScraper(), WamdaScraper(), ArabNetScraper()]:
            records = scraper.scrape_all()
            logger.info(f"[DRY RUN] {scraper.source_name}: {len(records)} records extracted")
            for r in records[:3]:
                logger.debug(f"  Sample: confidence={r.get('confidence')} startup='{r.get('startup_name')}' round='{r.get('round_type')}' amount=${r.get('amount_usd')}")
    else:
        stats = run_full_pipeline()
        logger.success(
            f"Pipeline complete: "
            f"fetched={stats['articles_fetched']} | "
            f"inserted={stats['rounds_inserted']} | "
            f"duplicates={stats['skipped_duplicates']} | "
            f"flagged={stats['low_confidence_flagged']}"
        )


def _run_single_source(source: str, dry_run: bool):
    from src.scraper.currency import ensure_rates_loaded
    ensure_rates_loaded()

    scrapers = {
        "menabytes": "src.scraper.menabytes.MENABytesScraper",
        "wamda": "src.scraper.wamda.WamdaScraper",
        "arabnet": "src.scraper.arabnet.ArabNetScraper",
    }

    module_path, class_name = scrapers[source].rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    scraper = getattr(module, class_name)()
    records = scraper.scrape_all()

    logger.info(f"Scraped {len(records)} records from {source}")

    if not dry_run:
        from src.database.writer import write_pipeline_results
        from src.database.connection import health_check
        if not health_check():
            logger.error("Cannot connect to database.")
            sys.exit(1)
        stats = write_pipeline_results(records)
        logger.success(f"Written: {stats}")
    else:
        logger.info("[DRY RUN] Not writing to DB")
        for r in records:
            logger.debug(f"  {r.get('startup_name')} | {r.get('round_type')} | ${r.get('amount_usd')} | conf={r.get('confidence')}")


if __name__ == "__main__":
    main()
