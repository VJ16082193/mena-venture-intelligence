"""
currency.py — Currency normalization utilities.

Static rates are used by default. If FX_API_KEY is set in the environment,
rates are refreshed from ExchangeRate-API on a configurable schedule.

All amounts stored in the database are normalized to USD.
"""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests
from loguru import logger

# ── Static fallback rates (updated Feb 2026) ──────────────────────────────────
_STATIC_RATES: dict[str, float] = {
    "USD": 1.0,
    "AED": 0.2723,   # UAE Dirham
    "SAR": 0.2666,   # Saudi Riyal
    "EGP": 0.0204,   # Egyptian Pound
    "QAR": 0.2747,   # Qatari Riyal
    "KWD": 3.2617,   # Kuwaiti Dinar
    "BHD": 2.6525,   # Bahraini Dinar
    "OMR": 2.5974,   # Omani Rial
    "JOD": 1.4104,   # Jordanian Dinar
    "EUR": 1.0820,   # Euro
    "GBP": 1.2680,   # British Pound
}

_RATES_CACHE_FILE = Path("logs/.fx_rates_cache.json")
_RATES: dict[str, float] = dict(_STATIC_RATES)  # working copy


def _load_cached_rates() -> bool:
    """Load rates from local cache file if it exists and is fresh enough."""
    refresh_days = int(os.getenv("FX_REFRESH_DAYS", "7"))
    if not _RATES_CACHE_FILE.exists():
        return False
    try:
        data = json.loads(_RATES_CACHE_FILE.read_text())
        cached_at = datetime.fromisoformat(data["cached_at"])
        if datetime.utcnow() - cached_at > timedelta(days=refresh_days):
            return False
        _RATES.update(data["rates"])
        logger.debug(f"FX rates loaded from cache (cached {cached_at.date()})")
        return True
    except Exception as e:
        logger.warning(f"Could not load FX cache: {e}")
        return False


def _fetch_live_rates(api_key: str) -> bool:
    """Fetch live rates from ExchangeRate-API and update the working copy."""
    url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/USD"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("result") != "success":
            logger.warning("ExchangeRate-API returned non-success result")
            return False

        new_rates = {k: 1.0 / v for k, v in data["conversion_rates"].items() if v > 0}
        new_rates["USD"] = 1.0
        _RATES.update(new_rates)

        _RATES_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _RATES_CACHE_FILE.write_text(
            json.dumps({"cached_at": datetime.utcnow().isoformat(), "rates": _RATES}, indent=2)
        )
        logger.info("FX rates refreshed from ExchangeRate-API")
        return True
    except Exception as e:
        logger.warning(f"Live FX fetch failed: {e}. Using static rates.")
        return False


def ensure_rates_loaded() -> None:
    """Call once at pipeline startup to ensure rates are as fresh as possible."""
    if _load_cached_rates():
        return
    api_key = os.getenv("FX_API_KEY", "").strip()
    if api_key:
        _fetch_live_rates(api_key)
    else:
        logger.info("FX_API_KEY not set — using bundled static rates")


def to_usd(amount: float, currency: str) -> Optional[float]:
    """
    Convert an amount in the given currency to USD.
    Returns None if the currency is not in the rates table.

    Args:
        amount:   The raw monetary value
        currency: 3-letter ISO 4217 currency code (e.g. "AED", "SAR")

    Returns:
        USD-equivalent float rounded to 2 decimal places, or None.
    """
    if amount <= 0:
        return None
    rate = _RATES.get(currency.upper())
    if rate is None:
        logger.warning(f"Unknown currency '{currency}' — cannot convert to USD")
        return None
    return round(amount * rate, 2)


def supported_currencies() -> list[str]:
    """Return list of supported currency codes."""
    return sorted(_RATES.keys())
