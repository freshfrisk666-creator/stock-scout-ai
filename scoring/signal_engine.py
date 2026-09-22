from __future__ import annotations

import pandas as pd


def rank_top10(technical: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    if technical.empty:
        return technical.copy()
    result = technical.sort_values(
        ["technical_score", "risk_reward", "ticker"],
        ascending=[False, False, True],
    ).reset_index(drop=True).copy()
    result["rank"] = result.index + 1
    return result.head(n)
