"""
tests/test_dedup.py — Unit tests for deduplication logic.

These tests mock the database session so no real DB is required.
Run: pytest tests/test_dedup.py -v
"""

from unittest.mock import MagicMock, patch

import pytest


# ── find_or_create_startup ─────────────────────────────────────────────────────

class TestFindOrCreateStartup:
    def _make_session(self, existing_rows):
        """Create a mock session returning the given rows on execute."""
        session = MagicMock()
        fetch_result = MagicMock()
        fetch_result.fetchall.return_value = existing_rows
        insert_result = MagicMock()
        insert_result.scalar.return_value = 99  # new ID

        def execute_side_effect(sql, params=None):
            sql_str = str(sql)
            if "SELECT id" in sql_str or "SELECT 1" in sql_str:
                return fetch_result
            return insert_result

        session.execute.side_effect = execute_side_effect
        return session

    def test_exact_match_returns_existing_id(self):
        from src.database.dedup import find_or_create_startup

        Row = MagicMock()
        Row.id = 42
        Row.name = "Tabby"
        session = self._make_session([Row])

        result = find_or_create_startup(session, "Tabby", "UAE")
        assert result == 42

    def test_fuzzy_match_returns_existing_id(self):
        """'Tabby.io' should match 'Tabby' with token_set_ratio >= 90."""
        from src.database.dedup import find_or_create_startup

        Row = MagicMock()
        Row.id = 42
        Row.name = "Tabby"
        session = self._make_session([Row])

        result = find_or_create_startup(session, "Tabby.io", "UAE")
        assert result == 42

    def test_no_match_creates_new(self):
        """'Completely Different Name' should not match 'Tabby'."""
        from src.database.dedup import find_or_create_startup

        Row = MagicMock()
        Row.id = 42
        Row.name = "Tabby"
        session = self._make_session([Row])

        # Override execute to return insert scalar for INSERT
        insert_result = MagicMock()
        insert_result.scalar.return_value = 99
        fetch_result = MagicMock()
        fetch_result.fetchall.return_value = [Row]

        call_count = [0]
        def execute_side_effect(sql, params=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return fetch_result
            return insert_result

        session.execute.side_effect = execute_side_effect

        result = find_or_create_startup(session, "Completely Different Corp", "UAE")
        assert result == 99

    def test_different_country_does_not_match(self):
        """
        Startups in different countries should not be merged even if name is similar.
        (The SELECT filters by country.)
        """
        from src.database.dedup import find_or_create_startup

        # Empty result for a different country
        session = self._make_session([])
        insert_result = MagicMock()
        insert_result.scalar.return_value = 100

        def execute_side_effect(sql, params=None):
            sql_str = str(sql)
            if "SELECT id" in sql_str:
                return MagicMock(fetchall=lambda: [])
            return insert_result

        session.execute.side_effect = execute_side_effect
        result = find_or_create_startup(session, "Tabby", "Egypt")
        assert result == 100


# ── article_exists ─────────────────────────────────────────────────────────────

class TestArticleExists:
    def test_returns_true_when_found(self):
        from src.database.dedup import article_exists

        session = MagicMock()
        session.execute.return_value.fetchone.return_value = (1,)
        assert article_exists(session, "https://example.com/article") is True

    def test_returns_false_when_not_found(self):
        from src.database.dedup import article_exists

        session = MagicMock()
        session.execute.return_value.fetchone.return_value = None
        assert article_exists(session, "https://example.com/new-article") is False


# ── funding_round_exists ───────────────────────────────────────────────────────

class TestFundingRoundExists:
    def test_returns_true_when_found(self):
        from src.database.dedup import funding_round_exists
        from datetime import date

        session = MagicMock()
        session.execute.return_value.fetchone.return_value = (1,)
        assert funding_round_exists(session, 1, "Seed", date(2024, 1, 1)) is True

    def test_returns_false_when_not_found(self):
        from src.database.dedup import funding_round_exists
        from datetime import date

        session = MagicMock()
        session.execute.return_value.fetchone.return_value = None
        assert funding_round_exists(session, 1, "Series A", date(2024, 6, 1)) is False
