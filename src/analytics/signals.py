"""
signals.py — Emerging deal signal detection.

Surfaces early-stage opportunities relevant to pre-emptive VC sourcing.
"""

from __future__ import annotations

import pandas as pd

from src.database.queries import get_emerging_signals


def early_stage_signals(max_amount_mn: float = 5.0, months: int = 6) -> pd.DataFrame:
    """
    Return a filtered, annotated DataFrame of early-stage deals.

    Annotations added:
    - signal_label: human-readable signal category
    - is_first_round: True if prior_rounds == 0
    """
    df = get_emerging_signals(max_amount_mn=max_amount_mn, months=months)
    if df.empty:
        return df

    df["is_first_round"] = df["prior_rounds"] == 0

    def label(row):
        if row["is_first_round"] and row["amount_mn_usd"] < 1.0:
            return "First Check"
        elif row["is_first_round"]:
            return "First Round"
        elif row["prior_rounds"] == 1:
            return "Follow-On Signal"
        else:
            return "Active"

    df["signal_label"] = df.apply(label, axis=1)
    return df.sort_values("announcement_date", ascending=False)
