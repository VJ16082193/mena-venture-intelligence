"""
tests/test_extractor.py — Unit tests for the extraction module.

Run: pytest tests/test_extractor.py -v
"""

import pytest
from src.scraper.extractor import (
    extract_amount,
    extract_round_type,
    extract_country,
    extract_sector,
    is_funding_article,
    compute_confidence,
    infer_investor_type,
)


# ── extract_amount ─────────────────────────────────────────────────────────────

class TestExtractAmount:
    def test_usd_million(self):
        amount, currency = extract_amount("The startup raised $5 million in funding.")
        assert amount == 5_000_000.0
        assert currency == "USD"

    def test_usd_billion(self):
        amount, currency = extract_amount("Valued at $1.2 billion after the round.")
        assert amount == 1_200_000_000.0
        assert currency == "USD"

    def test_abbreviated_mn(self):
        amount, currency = extract_amount("Secured $12mn in its Series B round.")
        assert amount == 12_000_000.0

    def test_aed_currency(self):
        amount, currency = extract_amount("The company raised AED 50 million.")
        assert amount == 50_000_000.0
        assert currency == "AED"

    def test_sar_currency(self):
        amount, currency = extract_amount("SAR 20 million funding announced.")
        assert amount == 20_000_000.0
        assert currency == "SAR"

    def test_no_amount(self):
        amount, currency = extract_amount("The startup announced a new product launch.")
        assert amount is None
        assert currency is None

    def test_comma_formatted(self):
        amount, currency = extract_amount("Raised $1,500 million in its IPO.")
        assert amount == 1_500_000_000.0

    def test_billion_abbreviation(self):
        amount, currency = extract_amount("Raised $2b in the latest round.")
        assert amount == 2_000_000_000.0


# ── extract_round_type ─────────────────────────────────────────────────────────

class TestExtractRoundType:
    def test_seed(self):
        assert extract_round_type("Announces $3M seed round") == "Seed"

    def test_series_a(self):
        assert extract_round_type("Closes $15M Series A funding") == "Series A"

    def test_series_b(self):
        assert extract_round_type("Series B round of $40M") == "Series B"

    def test_pre_seed(self):
        assert extract_round_type("Raises pre-seed funding of $500K") == "Pre-seed"

    def test_pre_seed_no_hyphen(self):
        assert extract_round_type("Completes a pre seed round") == "Pre-seed"

    def test_venture_debt(self):
        assert extract_round_type("Secures venture debt facility") == "Venture Debt"

    def test_no_match(self):
        assert extract_round_type("Company launches new product") is None

    def test_case_insensitive(self):
        assert extract_round_type("SERIES A funding secured") == "Series A"


# ── extract_country ────────────────────────────────────────────────────────────

class TestExtractCountry:
    def test_uae_keyword(self):
        assert extract_country("Dubai-based startup raises funding") == "UAE"

    def test_uae_explicit(self):
        assert extract_country("UAE fintech company secures investment") == "UAE"

    def test_saudi(self):
        assert extract_country("Riyadh startup closes Series A") == "Saudi Arabia"

    def test_egypt(self):
        assert extract_country("Cairo-headquartered logistics startup") == "Egypt"

    def test_qatar(self):
        assert extract_country("Doha-based company raises $10M") == "Qatar"

    def test_no_match(self):
        assert extract_country("London startup raises funding") is None


# ── extract_sector ─────────────────────────────────────────────────────────────

class TestExtractSector:
    def test_fintech(self):
        assert extract_sector("A payments startup in the UAE") == "Fintech"

    def test_healthtech(self):
        assert extract_sector("Digital health platform for the MENA region") == "Healthtech"

    def test_logistics(self):
        assert extract_sector("Last-mile delivery company raises funding") == "Logistics"

    def test_saas(self):
        assert extract_sector("B2B SaaS platform for restaurants") == "SaaS / Enterprise"

    def test_no_match(self):
        # Should return None for truly ambiguous text
        result = extract_sector("The company announced a new partnership")
        assert result is None


# ── is_funding_article ─────────────────────────────────────────────────────────

class TestIsFundingArticle:
    def test_clear_funding_signal(self):
        assert is_funding_article(
            "Dubai startup raises $5M seed round",
            "The company secured investment from leading venture capital firms."
        ) is True

    def test_not_funding(self):
        assert is_funding_article(
            "Top 10 restaurants to visit in Dubai",
            "Here are the best places to eat in the city this summer."
        ) is False

    def test_series_a_signal(self):
        assert is_funding_article(
            "Fintech raises Series A",
            "The $20 million investment will fund expansion."
        ) is True


# ── compute_confidence ─────────────────────────────────────────────────────────

class TestComputeConfidence:
    def test_full_record(self):
        record = {
            "startup_name": "TestCo",
            "round_type": "Seed",
            "amount_usd": 2_000_000,
            "announcement_date": "2024-01-15",
            "country": "UAE",
            "investors": [{"name": "BECO Capital", "lead": True}],
        }
        score = compute_confidence(record)
        assert score == 100

    def test_minimal_record(self):
        record = {"startup_name": "TestCo"}
        score = compute_confidence(record)
        assert score == 25

    def test_empty_record(self):
        assert compute_confidence({}) == 0

    def test_partial_record(self):
        record = {"startup_name": "TestCo", "round_type": "Seed", "amount_usd": 1_000_000}
        score = compute_confidence(record)
        assert score == 65  # 25 + 20 + 20


# ── infer_investor_type ────────────────────────────────────────────────────────

class TestInferInvestorType:
    def test_vc(self):
        assert infer_investor_type("STV Capital") == "VC"

    def test_vc_ventures(self):
        assert infer_investor_type("Global Ventures") == "VC"

    def test_corporate(self):
        assert infer_investor_type("Aramco Technologies Corp") == "Corporate"

    def test_government(self):
        assert infer_investor_type("Mubadala Government Fund") == "Government"

    def test_angel_fallback(self):
        assert infer_investor_type("John Smith") == "Angel"
