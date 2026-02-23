"""
tests/test_validation.py — Unit tests for data validation.

Run: pytest tests/test_validation.py -v
"""

from datetime import date, timedelta

import pytest

from src.database.validation import validate_record


class TestValidateRecord:
    def _base_record(self):
        return {
            "url": "https://menabytes.com/tabby-raises-5m-seed/",
            "title": "Tabby raises $5M Seed round",
            "publication_date": date.today() - timedelta(days=10),
            "amount_usd": 5_000_000.0,
            "startup_name": "Tabby",
            "round_type": "Seed",
            "country": "UAE",
        }

    def test_valid_record_no_errors(self):
        errors = validate_record(self._base_record())
        assert errors == []

    def test_missing_url(self):
        r = self._base_record()
        r["url"] = ""
        errors = validate_record(r)
        assert any("URL" in e for e in errors)

    def test_invalid_url_scheme(self):
        r = self._base_record()
        r["url"] = "ftp://bad-scheme.com/article"
        errors = validate_record(r)
        assert any("scheme" in e.lower() for e in errors)

    def test_empty_title(self):
        r = self._base_record()
        r["title"] = "   "
        errors = validate_record(r)
        assert any("title" in e.lower() for e in errors)

    def test_future_date(self):
        r = self._base_record()
        r["publication_date"] = date.today() + timedelta(days=5)
        errors = validate_record(r)
        assert any("future" in e.lower() for e in errors)

    def test_negative_amount(self):
        r = self._base_record()
        r["amount_usd"] = -1_000_000
        errors = validate_record(r)
        assert any("positive" in e.lower() for e in errors)

    def test_amount_exceeds_sanity_cap(self):
        r = self._base_record()
        r["amount_usd"] = 15_000_000_000  # $15B
        errors = validate_record(r)
        assert any("sanity cap" in e.lower() for e in errors)

    def test_startup_name_too_short(self):
        r = self._base_record()
        r["startup_name"] = "X"
        errors = validate_record(r)
        assert any("too short" in e.lower() for e in errors)

    def test_none_amount_is_valid(self):
        """amount_usd can be None (undisclosed rounds)."""
        r = self._base_record()
        r["amount_usd"] = None
        errors = validate_record(r)
        assert errors == []

    def test_none_date_is_valid(self):
        """publication_date can be None (missing from article)."""
        r = self._base_record()
        r["publication_date"] = None
        errors = validate_record(r)
        assert errors == []
