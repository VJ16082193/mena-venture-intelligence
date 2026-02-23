"""
dedup.py — Entity deduplication using fuzzy string matching.

Strategy:
  - Articles:       UNIQUE constraint on url column (handled at DB level)
  - Startups:       fuzzy name + exact country match (threshold: 90)
  - Investors:      fuzzy name match across all investors (threshold: 88)
  - Funding rounds: UNIQUE constraint on (startup_id, round_type, announcement_date)
"""

from typing import Optional

from loguru import logger
from rapidfuzz import fuzz
from sqlalchemy import text
from sqlalchemy.orm import Session

# Tunable thresholds
STARTUP_MATCH_THRESHOLD = 90
INVESTOR_MATCH_THRESHOLD = 88


def find_or_create_startup(
    session: Session,
    name: str,
    country: str,
    sector: Optional[str] = None,
    description: Optional[str] = None,
) -> int:
    """
    Return the ID of a matching startup, or create a new one.

    Matching logic: token_set_ratio >= STARTUP_MATCH_THRESHOLD AND same country.
    This handles common variants: "Tabby" == "Tabby.io", "Noon" == "Noon.com"
    """
    rows = session.execute(
        text("SELECT id, name FROM startups WHERE country = :country"),
        {"country": country},
    ).fetchall()

    for row in rows:
        score = fuzz.token_set_ratio(name.lower(), row.name.lower())
        if score >= STARTUP_MATCH_THRESHOLD:
            logger.debug(f"Startup match: '{name}' → '{row.name}' (score={score}, id={row.id})")
            return row.id

    # No match — create new record
    result = session.execute(
        text(
            """
            INSERT INTO startups (name, country, sector, description)
            VALUES (:name, :country, :sector, :description)
            RETURNING id
            """
        ),
        {"name": name, "country": country, "sector": sector, "description": description},
    )
    new_id = result.scalar()
    logger.info(f"New startup created: '{name}' ({country}) id={new_id}")
    return new_id


def find_or_create_investor(session: Session, name: str, inv_type: Optional[str] = None) -> int:
    """
    Return the ID of a matching investor, or create a new one.

    Matching logic: token_set_ratio >= INVESTOR_MATCH_THRESHOLD (global, no country constraint).
    Handles: "BECO Capital" == "BECO Capital Partners"
    """
    rows = session.execute(text("SELECT id, name FROM investors")).fetchall()

    for row in rows:
        score = fuzz.token_set_ratio(name.lower(), row.name.lower())
        if score >= INVESTOR_MATCH_THRESHOLD:
            logger.debug(f"Investor match: '{name}' → '{row.name}' (score={score}, id={row.id})")
            return row.id

    result = session.execute(
        text("INSERT INTO investors (name, type) VALUES (:name, :type) RETURNING id"),
        {"name": name, "type": inv_type},
    )
    new_id = result.scalar()
    logger.info(f"New investor created: '{name}' (type={inv_type}) id={new_id}")
    return new_id


def article_exists(session: Session, url: str) -> bool:
    """Return True if an article with this URL already exists in the DB."""
    result = session.execute(
        text("SELECT 1 FROM articles WHERE url = :url LIMIT 1"),
        {"url": url},
    ).fetchone()
    return result is not None


def funding_round_exists(
    session: Session,
    startup_id: int,
    round_type: str,
    announcement_date,
) -> bool:
    """Return True if this exact round (startup + type + date) already exists."""
    result = session.execute(
        text(
            """
            SELECT 1 FROM funding_rounds
            WHERE startup_id = :sid
              AND round_type  = :rtype
              AND announcement_date = :adate
            LIMIT 1
            """
        ),
        {"sid": startup_id, "rtype": round_type, "adate": announcement_date},
    ).fetchone()
    return result is not None
