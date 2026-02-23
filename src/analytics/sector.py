"""
sector.py — Sector momentum analytics.

Computes derived metrics on top of the raw query results from queries.py.
"""

from __future__ import annotations

import pandas as pd

from src.database.queries import get_sector_summary, get_sector_momentum


def sector_summary_with_share(
    countries=None, date_from=None, date_to=None
) -> pd.DataFrame:
    """
    Returns sector summary enriched with:
    - capital_share_pct: each sector's % of total capital
    - deal_share_pct: each sector's % of total deals
    """
    df = get_sector_summary(countries=countries, date_from=date_from, date_to=date_to)
    if df.empty:
        return df

    total_capital = df["total_capital_mn"].sum()
    total_deals = df["deal_count"].sum()

    df["capital_share_pct"] = (
        (df["total_capital_mn"] / total_capital * 100).round(1)
        if total_capital > 0 else 0
    )
    df["deal_share_pct"] = (
        (df["deal_count"] / total_deals * 100).round(1)
        if total_deals > 0 else 0
    )
    return df


def top_sectors_by_momentum(top_n: int = 5) -> pd.DataFrame:
    """
    Return top N sectors ranked by recent 6-month capital growth rate.
    Filters out sectors with no recent activity.
    """
    df = get_sector_momentum()
    df = df[df["recent_6m_mn"] > 0].copy()
    df = df.sort_values("growth_pct", ascending=False, na_position="last")
    return df.head(top_n)
