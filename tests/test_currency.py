"""
tests/test_currency.py — Unit tests for currency normalization.

Run: pytest tests/test_currency.py -v
"""

import pytest
from src.scraper.currency import to_usd, supported_currencies


class TestToUsd:
    def test_usd_passthrough(self):
        assert to_usd(1_000_000, "USD") == 1_000_000.0

    def test_aed_conversion(self):
        result = to_usd(1_000_000, "AED")
        assert result is not None
        assert 200_000 < result < 400_000  # rough range for AED→USD

    def test_sar_conversion(self):
        result = to_usd(1_000_000, "SAR")
        assert result is not None
        assert 200_000 < result < 400_000

    def test_kwd_is_strong(self):
        """Kuwaiti Dinar is one of the strongest currencies — 1 KWD > 3 USD."""
        result = to_usd(1_000_000, "KWD")
        assert result is not None
        assert result > 3_000_000

    def test_unknown_currency_returns_none(self):
        assert to_usd(1_000_000, "XYZ") is None

    def test_zero_amount_returns_none(self):
        assert to_usd(0, "USD") is None

    def test_negative_amount_returns_none(self):
        assert to_usd(-500_000, "USD") is None

    def test_case_insensitive(self):
        result_upper = to_usd(1_000_000, "AED")
        result_lower = to_usd(1_000_000, "aed")
        assert result_upper == result_lower

    def test_rounding(self):
        """Result should be rounded to 2 decimal places."""
        result = to_usd(1, "AED")
        assert result == round(result, 2)


class TestSupportedCurrencies:
    def test_includes_core_mena_currencies(self):
        supported = supported_currencies()
        for code in ["USD", "AED", "SAR", "EGP", "QAR", "KWD", "BHD"]:
            assert code in supported

    def test_returns_sorted_list(self):
        supported = supported_currencies()
        assert supported == sorted(supported)
