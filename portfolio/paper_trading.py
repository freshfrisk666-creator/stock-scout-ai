from __future__ import annotations

import math
import pandas as pd


def build_equal_weight_orders(top10: pd.DataFrame, starting_cash: float = 100_000, positions: int = 10) -> pd.DataFrame:
    if top10.empty:
        return pd.DataFrame()
    capital_per_position = starting_cash / max(1, positions)
    cash = float(starting_cash)
    rows = []
    for _, row in top10.head(positions).iterrows():
        entry = float(row["entry"])
        shares = math.floor(capital_per_position / entry)
        notional = shares * entry
        cash -= notional
        rows.append({
            "rank": int(row["rank"]),
            "ticker": row["ticker"],
            "entry": entry,
            "shares": shares,
            "notional": notional,
            "stop": float(row["stop"]),
            "target": float(row["target"]),
            "cash_remaining": cash,
        })
    return pd.DataFrame(rows)
