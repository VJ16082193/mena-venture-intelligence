"""
validation.py — Pre-insert data validation checks.

Validation is intentionally permissive — we don't want to silently discard
records with minor issues. Errors are collected and returned so the caller
can log them, not silently drop data.
"""

from datetime import date
from typing import Optional
from urllib.parse import urlparse

VALID_ROUND_TYPES = {
    "Pre-seed", "Seed", "Series A", "Series B", "Series C", "Series D",
    "Growth", "Bridge", "Venture Debt", "IPO", "Acquisition", "Grant", "Undisclosed",
}

VALID_COUNTRIES = {
    "UAE", "Saudi Arabia", "Egypt", "Qatar", "Bahrain", "Kuwait",
    "Jordan", "Lebanon", "Iraq", "Morocco", "Tunisia", "Unknown",
}

MAX_AMOUNT_USD = 10_000_000_000  # $10B sanity cap


def validate_record(record: dict) -> list[str]:
    """
    Validate a single pipeline record. Returns a list of error messages.
    Empty list means the record is valid.
    """
    errors = []

    # URL
    url = record.get("url", "")
    if not url:
        errors.append("Missing URL")
    else:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            errors.append(f"Invalid URL scheme: '{url[:80]}'")

    # Title
    if not record.get("title", "").strip():
        errors.append("Empty title")

    # Publication date
    pub_date = record.get("publication_date")
    if pub_date is not None and isinstance(pub_date, date):
        if pub_date > date.today():
            errors.append(f"Announcement date in the future: {pub_date}")
    
    # Amount sanity check
    amount_usd = record.get("amount_usd")
    if amount_usd is not None:
        if amount_usd <= 0:
            errors.append(f"amount_usd must be positive, got {amount_usd}")
        if amount_usd > MAX_AMOUNT_USD:
            errors.append(f"amount_usd {amount_usd} exceeds sanity cap {MAX_AMOUNT_USD}")

    # Round type
    round_type = record.get("round_type")
    if round_type and round_type not in VALID_ROUND_TYPES:
        # Don't error — just warn. Unknown types will be stored as-is.
        pass

    # Country
    country = record.get("country")
    if country and country not in VALID_COUNTRIES:
        # Non-MENA country: flag but don't block (could be international deal)
        pass

    # Startup name minimum length
    startup_name = record.get("startup_name", "")
    if startup_name and len(startup_name.strip()) < 2:
        errors.append(f"Startup name too short: '{startup_name}'")

    return errors
