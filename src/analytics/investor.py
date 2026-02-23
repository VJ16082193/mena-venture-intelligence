"""
investor.py — Investor activity analytics.
"""

from __future__ import annotations

import pandas as pd

from src.database.queries import get_investor_leaderboard, get_coinvestment_pairs


def investor_leaderboard_enriched(
    countries=None, date_from=None, date_to=None
) -> pd.DataFrame:
    """
    Returns investor leaderboard with lead_ratio and avg_check_size columns.
    """
    df = get_investor_leaderboard(countries=countries, date_from=date_from, date_to=date_to)
    if df.empty:
        return df

    df["lead_ratio_pct"] = (
        (df["lead_deals"] / df["total_deals"] * 100)
        .round(0)
        .astype(int)
    )
    df["avg_check_mn"] = (df["deployed_mn_usd"] / df["total_deals"]).round(2)
    return df


def coinvestment_network_edges(min_count: int = 2) -> list[dict]:
    """
    Return co-investment pairs as a list of edge dicts suitable for graph rendering.
    Format: [{source, target, weight}, ...]
    """
    df = get_coinvestment_pairs(min_count=min_count)
    return [
        {"source": row["investor_a"], "target": row["investor_b"], "weight": row["co_investments"]}
        for _, row in df.iterrows()
    ]
