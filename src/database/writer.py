"""
writer.py — Persist pipeline results to PostgreSQL.

Handles article insertion, deduplication, and cascading inserts
for startups, funding rounds, and investors.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from loguru import logger
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.database.connection import get_session
from src.database.dedup import (
    article_exists,
    find_or_create_investor,
    find_or_create_startup,
    funding_round_exists,
)
from src.database.validation import validate_record


def write_pipeline_results(records: list[dict]) -> dict:
    """
    Write a list of extracted funding records to the database.

    Each record should come from a scraper's parse_article() method.
    Returns stats dict: {rounds_inserted, skipped_duplicates, validation_errors}
    """
    stats = {"rounds_inserted": 0, "skipped_duplicates": 0, "validation_errors": 0}

    for record in records:
        try:
            result = _write_single_record(record)
            if result == "inserted":
                stats["rounds_inserted"] += 1
            elif result == "duplicate":
                stats["skipped_duplicates"] += 1
            elif result == "invalid":
                stats["validation_errors"] += 1
        except Exception as e:
            logger.error(f"Unexpected error writing record '{record.get('title', '')[:60]}': {e}")

    return stats


def _write_single_record(record: dict) -> str:
    """
    Write a single pipeline record. Returns 'inserted', 'duplicate', or 'invalid'.
    """
    # Validate first
    errors = validate_record(record)
    if errors:
        logger.warning(f"Validation failed for '{record.get('title', '')[:60]}': {errors}")
        return "invalid"

    url = record.get("url", "")
    startup_name = record.get("startup_name") or "Unknown"
    country = record.get("country") or "Unknown"

    with get_session() as session:
        # ── 1. Article (URL dedup at DB level) ────────────────────────────────
        if article_exists(session, url):
            logger.debug(f"Skipping duplicate article: {url}")
            return "duplicate"

        article_id = _insert_article(session, record)

        # ── 2. Startup (fuzzy dedup) ───────────────────────────────────────────
        startup_id = find_or_create_startup(
            session,
            name=startup_name,
            country=country,
            sector=record.get("sector"),
            description=record.get("description"),
        )

        # ── 3. Funding round (exact dedup) ────────────────────────────────────
        round_type = record.get("round_type") or "Undisclosed"
        ann_date = record.get("publication_date") or date.today()

        if funding_round_exists(session, startup_id, round_type, ann_date):
            logger.debug(f"Skipping duplicate round: {startup_name} / {round_type} / {ann_date}")
            return "duplicate"

        round_id = _insert_funding_round(session, startup_id, article_id, record)

        # ── 4. Investors ───────────────────────────────────────────────────────
        for inv in record.get("investors", []):
            _insert_investor_link(session, round_id, inv)

        # ── 5. Mark article as processed ──────────────────────────────────────
        session.execute(
            text("UPDATE articles SET processed_flag = TRUE WHERE id = :id"),
            {"id": article_id},
        )

    return "inserted"


# ── Private helpers ───────────────────────────────────────────────────────────

def _insert_article(session, record: dict) -> int:
    result = session.execute(
        text(
            """
            INSERT INTO articles (title, source, url, publication_date, raw_content, extraction_confidence)
            VALUES (:title, :source, :url, :pub_date, :raw_content, :confidence)
            ON CONFLICT (url) DO NOTHING
            RETURNING id
            """
        ),
        {
            "title": record.get("title", "")[:500],
            "source": record.get("source", ""),
            "url": record.get("url", ""),
            "pub_date": record.get("publication_date"),
            "raw_content": record.get("raw_content", "")[:5000],
            "confidence": record.get("confidence"),
        },
    )
    row = result.fetchone()
    if row:
        return row[0]
    # If ON CONFLICT fired, fetch the existing id
    existing = session.execute(
        text("SELECT id FROM articles WHERE url = :url"), {"url": record.get("url")}
    ).fetchone()
    return existing[0] if existing else None


def _insert_funding_round(session, startup_id: int, article_id: Optional[int], record: dict) -> int:
    result = session.execute(
        text(
            """
            INSERT INTO funding_rounds
                (startup_id, round_type, amount_usd, amount_original,
                 currency_original, announcement_date, article_id)
            VALUES
                (:startup_id, :round_type, :amount_usd, :amount_original,
                 :currency_original, :announcement_date, :article_id)
            RETURNING id
            """
        ),
        {
            "startup_id": startup_id,
            "round_type": record.get("round_type") or "Undisclosed",
            "amount_usd": record.get("amount_usd"),
            "amount_original": record.get("amount_raw"),
            "currency_original": record.get("currency"),
            "announcement_date": record.get("publication_date") or date.today(),
            "article_id": article_id,
        },
    )
    return result.scalar()


def _insert_investor_link(session, round_id: int, inv: dict) -> None:
    investor_id = find_or_create_investor(
        session, name=inv["name"], inv_type=inv.get("type")
    )
    try:
        session.execute(
            text(
                """
                INSERT INTO funding_round_investors (funding_round_id, investor_id, lead_investor)
                VALUES (:round_id, :investor_id, :lead)
                ON CONFLICT DO NOTHING
                """
            ),
            {"round_id": round_id, "investor_id": investor_id, "lead": inv.get("lead", False)},
        )
    except IntegrityError:
        session.rollback()
        logger.debug(f"Skipped duplicate investor link round={round_id} investor={investor_id}")
