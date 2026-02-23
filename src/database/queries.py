"""
queries.py — All parameterized analytics queries used by the dashboard.

All functions accept optional filter parameters and return pandas DataFrames.
Results are not cached here — caching is handled at the Streamlit layer with @st.cache_data.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd
from sqlalchemy import text

from src.database.connection import get_session

# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_filter_clause(
    countries: Optional[list[str]] = None,
    sectors: Optional[list[str]] = None,
    round_types: Optional[list[str]] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    table_alias: str = "",
) -> tuple[str, dict]:
    """
    Build a WHERE clause fragment and params dict from optional filter lists.
    Returns ("AND col IN (...) ...", {params}).
    """
    clauses = []
    params = {}
    ta = f"{table_alias}." if table_alias else ""

    if date_from:
        clauses.append(f"{ta}announcement_date >= :date_from")
        params["date_from"] = date_from
    if date_to:
        clauses.append(f"{ta}announcement_date <= :date_to")
        params["date_to"] = date_to
    if countries:
        clauses.append("s.country = ANY(:countries)")
        params["countries"] = countries
    if sectors:
        clauses.append("s.sector = ANY(:sectors)")
        params["sectors"] = sectors
    if round_types:
        clauses.append(f"{ta}round_type = ANY(:round_types)")
        params["round_types"] = round_types

    clause = ("AND " + " AND ".join(clauses)) if clauses else ""
    return clause, params


def _run(sql: str, params: dict) -> pd.DataFrame:
    with get_session() as session:
        result = session.execute(text(sql), params)
        rows = result.fetchall()
        columns = list(result.keys())
    return pd.DataFrame(rows, columns=columns)


# ── Overview KPIs ─────────────────────────────────────────────────────────────

def get_overview_kpis(
    countries=None, sectors=None, round_types=None,
    date_from=None, date_to=None
) -> dict:
    """Return scalar KPIs for the summary cards."""
    filter_clause, params = _build_filter_clause(
        countries, sectors, round_types, date_from, date_to, table_alias="fr"
    )
    sql = f"""
        SELECT
            COUNT(fr.id)                                    AS total_deals,
            COALESCE(SUM(fr.amount_usd), 0) / 1e6         AS total_capital_mn,
            COALESCE(AVG(fr.amount_usd), 0) / 1e6         AS avg_deal_mn,
            COUNT(DISTINCT fri.investor_id)                AS active_investors
        FROM funding_rounds fr
        JOIN startups s ON s.id = fr.startup_id
        LEFT JOIN funding_round_investors fri ON fri.funding_round_id = fr.id
        WHERE 1=1 {filter_clause}
    """
    df = _run(sql, params)
    if df.empty:
        return {"total_deals": 0, "total_capital_mn": 0.0, "avg_deal_mn": 0.0, "active_investors": 0}
    row = df.iloc[0]
    return {
        "total_deals": int(row["total_deals"] or 0),
        "total_capital_mn": float(row["total_capital_mn"] or 0),
        "avg_deal_mn": float(row["avg_deal_mn"] or 0),
        "active_investors": int(row["active_investors"] or 0),
    }


# ── Monthly Trend ─────────────────────────────────────────────────────────────

def get_monthly_trend(
    countries=None, sectors=None, round_types=None,
    date_from=None, date_to=None
) -> pd.DataFrame:
    """Monthly deal count and capital, for the line chart."""
    filter_clause, params = _build_filter_clause(
        countries, sectors, round_types, date_from, date_to, table_alias="fr"
    )
    sql = f"""
        SELECT
            DATE_TRUNC('month', fr.announcement_date)::date  AS month,
            COUNT(fr.id)                                      AS deal_count,
            COALESCE(SUM(fr.amount_usd), 0) / 1e6           AS total_mn_usd,
            COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP
                (ORDER BY fr.amount_usd), 0) / 1e6           AS median_deal_mn_usd
        FROM funding_rounds fr
        JOIN startups s ON s.id = fr.startup_id
        WHERE 1=1 {filter_clause}
        GROUP BY DATE_TRUNC('month', fr.announcement_date)
        ORDER BY month
    """
    return _run(sql, params)


# ── Sector Summary ────────────────────────────────────────────────────────────

def get_sector_summary(
    countries=None, date_from=None, date_to=None
) -> pd.DataFrame:
    """Total capital and deal count by sector."""
    filter_clause, params = _build_filter_clause(
        countries=countries, date_from=date_from, date_to=date_to, table_alias="fr"
    )
    sql = f"""
        SELECT
            COALESCE(s.sector, 'Other')                    AS sector,
            COUNT(fr.id)                                    AS deal_count,
            COALESCE(SUM(fr.amount_usd), 0) / 1e6         AS total_capital_mn,
            COALESCE(AVG(fr.amount_usd), 0) / 1e6         AS avg_deal_mn
        FROM funding_rounds fr
        JOIN startups s ON s.id = fr.startup_id
        WHERE 1=1 {filter_clause}
        GROUP BY s.sector
        ORDER BY total_capital_mn DESC
    """
    return _run(sql, params)


# ── Sector Momentum (growth rate) ─────────────────────────────────────────────

def get_sector_momentum() -> pd.DataFrame:
    """Compare last 6 months vs prior 6 months for growth rate calculation."""
    sql = """
        SELECT
            COALESCE(s.sector, 'Other')                                    AS sector,
            SUM(CASE WHEN fr.announcement_date >= NOW() - INTERVAL '6 months'
                     THEN fr.amount_usd ELSE 0 END) / 1e6                  AS recent_6m_mn,
            SUM(CASE WHEN fr.announcement_date <  NOW() - INTERVAL '6 months'
                      AND fr.announcement_date >= NOW() - INTERVAL '12 months'
                     THEN fr.amount_usd ELSE 0 END) / 1e6                  AS prior_6m_mn
        FROM funding_rounds fr
        JOIN startups s ON s.id = fr.startup_id
        WHERE fr.announcement_date >= NOW() - INTERVAL '12 months'
        GROUP BY s.sector
        ORDER BY recent_6m_mn DESC
    """
    df = _run(sql, {})
    df["growth_pct"] = df.apply(
        lambda r: ((r["recent_6m_mn"] - r["prior_6m_mn"]) / r["prior_6m_mn"] * 100)
        if r["prior_6m_mn"] > 0 else None,
        axis=1,
    )
    return df


# ── Investor Leaderboard ──────────────────────────────────────────────────────

def get_investor_leaderboard(
    countries=None, date_from=None, date_to=None, limit: int = 25
) -> pd.DataFrame:
    """Top investors by deal count."""
    filter_clause, params = _build_filter_clause(
        countries=countries, date_from=date_from, date_to=date_to, table_alias="fr"
    )
    params["limit"] = limit
    sql = f"""
        SELECT
            i.name                                                  AS investor,
            COALESCE(i.type, 'Unknown')                            AS type,
            COUNT(fri.id)                                           AS total_deals,
            SUM(CASE WHEN fri.lead_investor THEN 1 ELSE 0 END)     AS lead_deals,
            COALESCE(SUM(fr.amount_usd), 0) / 1e6                 AS deployed_mn_usd,
            MIN(fr.announcement_date)                               AS first_deal,
            MAX(fr.announcement_date)                               AS latest_deal
        FROM investors i
        JOIN funding_round_investors fri ON fri.investor_id = i.id
        JOIN funding_rounds fr ON fr.id = fri.funding_round_id
        JOIN startups s ON s.id = fr.startup_id
        WHERE 1=1 {filter_clause}
        GROUP BY i.id, i.name, i.type
        ORDER BY total_deals DESC
        LIMIT :limit
    """
    return _run(sql, params)


# ── Co-investment Pairs ───────────────────────────────────────────────────────

def get_coinvestment_pairs(min_count: int = 2) -> pd.DataFrame:
    """Pairs of investors who have co-invested in 2+ deals."""
    sql = """
        SELECT
            a.name  AS investor_a,
            b.name  AS investor_b,
            COUNT(*) AS co_investments
        FROM funding_round_investors x
        JOIN funding_round_investors y
            ON x.funding_round_id = y.funding_round_id
            AND x.investor_id < y.investor_id
        JOIN investors a ON a.id = x.investor_id
        JOIN investors b ON b.id = y.investor_id
        GROUP BY a.name, b.name
        HAVING COUNT(*) >= :min_count
        ORDER BY co_investments DESC
        LIMIT 50
    """
    return _run(sql, {"min_count": min_count})


# ── Geography ─────────────────────────────────────────────────────────────────

def get_geography_summary(date_from=None, date_to=None) -> pd.DataFrame:
    """Capital deployed and deal count by country."""
    filter_clause, params = _build_filter_clause(date_from=date_from, date_to=date_to, table_alias="fr")
    sql = f"""
        SELECT
            s.country,
            COUNT(fr.id)                                    AS deal_count,
            COALESCE(SUM(fr.amount_usd), 0) / 1e6         AS total_capital_mn,
            COALESCE(AVG(fr.amount_usd), 0) / 1e6         AS avg_deal_mn,
            COUNT(DISTINCT s.sector)                        AS active_sectors
        FROM funding_rounds fr
        JOIN startups s ON s.id = fr.startup_id
        WHERE 1=1 {filter_clause}
        GROUP BY s.country
        ORDER BY total_capital_mn DESC
    """
    return _run(sql, params)


def get_stage_by_country() -> pd.DataFrame:
    """Deal count by country and round stage."""
    sql = """
        SELECT
            s.country,
            fr.round_type,
            COUNT(*) AS deals
        FROM funding_rounds fr
        JOIN startups s ON s.id = fr.startup_id
        GROUP BY s.country, fr.round_type
        ORDER BY s.country, deals DESC
    """
    return _run(sql, {})


# ── Recent Deals Feed ─────────────────────────────────────────────────────────

def get_recent_deals(
    countries=None, sectors=None, round_types=None,
    date_from=None, date_to=None, limit: int = 50
) -> pd.DataFrame:
    """Latest deals for the deal feed table."""
    filter_clause, params = _build_filter_clause(
        countries, sectors, round_types, date_from, date_to, table_alias="fr"
    )
    params["limit"] = limit
    sql = f"""
        SELECT
            s.name                          AS startup,
            s.country,
            COALESCE(s.sector, '—')        AS sector,
            fr.round_type,
            COALESCE(fr.amount_usd / 1e6, 0) AS amount_mn_usd,
            fr.announcement_date,
            a.url                           AS source_url,
            a.source
        FROM funding_rounds fr
        JOIN startups s ON s.id = fr.startup_id
        LEFT JOIN articles a ON a.id = fr.article_id
        WHERE 1=1 {filter_clause}
        ORDER BY fr.announcement_date DESC
        LIMIT :limit
    """
    return _run(sql, params)


# ── Emerging Signals ──────────────────────────────────────────────────────────

def get_emerging_signals(max_amount_mn: float = 5.0, months: int = 6) -> pd.DataFrame:
    """Early-stage deals under $5M in the last N months."""
    sql = """
        SELECT
            s.name                              AS startup,
            s.country,
            COALESCE(s.sector, '—')            AS sector,
            fr.round_type,
            fr.amount_usd / 1e6               AS amount_mn_usd,
            fr.announcement_date,
            COUNT(fr2.id)                       AS prior_rounds,
            a.url                               AS source_url
        FROM funding_rounds fr
        JOIN startups s ON s.id = fr.startup_id
        LEFT JOIN funding_rounds fr2
            ON fr2.startup_id = s.id
            AND fr2.announcement_date < fr.announcement_date
        LEFT JOIN articles a ON a.id = fr.article_id
        WHERE fr.announcement_date >= NOW() - (:months || ' months')::interval
          AND (fr.amount_usd IS NULL OR fr.amount_usd < :max_amount)
          AND fr.round_type IN ('Pre-seed', 'Seed', 'Undisclosed')
        GROUP BY s.name, s.country, s.sector, fr.round_type,
                 fr.amount_usd, fr.announcement_date, a.url
        ORDER BY fr.announcement_date DESC
        LIMIT 100
    """
    return _run(sql, {"months": months, "max_amount": max_amount_mn * 1_000_000})


# ── Search ────────────────────────────────────────────────────────────────────

def search_startups(query: str) -> pd.DataFrame:
    """Full-text startup name search using ILIKE."""
    return _run(
        """
        SELECT s.id, s.name, s.country, s.sector, s.founded_year,
               COUNT(fr.id) AS total_rounds,
               COALESCE(SUM(fr.amount_usd), 0) / 1e6 AS total_raised_mn
        FROM startups s
        LEFT JOIN funding_rounds fr ON fr.startup_id = s.id
        WHERE s.name ILIKE :q
        GROUP BY s.id
        ORDER BY total_raised_mn DESC
        LIMIT 20
        """,
        {"q": f"%{query}%"},
    )


def search_investors(query: str) -> pd.DataFrame:
    """Full-text investor name search."""
    return _run(
        """
        SELECT i.id, i.name, i.type, i.country,
               COUNT(fri.id) AS total_deals
        FROM investors i
        LEFT JOIN funding_round_investors fri ON fri.investor_id = i.id
        WHERE i.name ILIKE :q
        GROUP BY i.id
        ORDER BY total_deals DESC
        LIMIT 20
        """,
        {"q": f"%{query}%"},
    )
