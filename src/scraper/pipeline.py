"""
pipeline.py — Orchestrates the full scrape → extract → clean → store pipeline.

Called by main.py on a schedule and by scripts/run_pipeline.py for manual runs.
Returns a stats dict summarizing the run.
"""

from __future__ import annotations

import os
from typing import Optional

from loguru import logger

from src.scraper.currency import ensure_rates_loaded
from src.scraper.menabytes import MENABytesScraper
from src.scraper.wamda import WamdaScraper
from src.scraper.arabnet import ArabNetScraper
from src.database.writer import write_pipeline_results
from src.database.connection import get_session


def run_full_pipeline() -> dict:
    """
    Execute the full pipeline across all configured scrapers.

    Returns:
        dict with keys: articles_fetched, rounds_inserted,
                        skipped_duplicates, low_confidence_flagged
    """
    ensure_rates_loaded()

    scrapers = [
        MENABytesScraper(),
        WamdaScraper(),
        ArabNetScraper(),
    ]

    min_confidence = int(os.getenv("MIN_CONFIDENCE_SCORE", "40"))
    all_records: list[dict] = []

    for scraper in scrapers:
        try:
            records = scraper.scrape_all()
            all_records.extend(records)
        except Exception as e:
            logger.error(f"Scraper {scraper.source_name} failed entirely: {e}")

    logger.info(f"Total raw records collected: {len(all_records)}")

    # Split by confidence
    high_conf = [r for r in all_records if r.get("confidence", 0) >= min_confidence]
    low_conf = [r for r in all_records if r.get("confidence", 0) < min_confidence]

    if low_conf:
        logger.warning(
            f"{len(low_conf)} records below confidence threshold "
            f"({min_confidence}) — flagged for review"
        )
        _log_low_confidence(low_conf)

    # Write to database
    stats = {"articles_fetched": len(all_records), "low_confidence_flagged": len(low_conf)}
    db_stats = write_pipeline_results(high_conf)
    stats.update(db_stats)

    return stats


def _log_low_confidence(records: list[dict]) -> None:
    """Log low-confidence records for manual review."""
    for r in records:
        logger.warning(
            f"LOW_CONFIDENCE score={r.get('confidence')} | "
            f"title='{r.get('title', '')[:80]}' | "
            f"url={r.get('url', '')}"
        )
