from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .trade_analysis import load_closed_trade_analysis


SIGNAL_SCORE_FIELDS = [
    "technical_score",
    "trend_score",
    "momentum_score",
    "rsi_score",
    "volume_score",
    "breakout_score",
]


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _max_drawdown_from_pnl(pnl_series: pd.Series) -> float:
    """Maximum drawdown of cumulative realized P&L, in currency units."""
    if pnl_series.empty:
        return 0.0
    cumulative = pnl_series.fillna(0.0).cumsum()
    running_peak = cumulative.cummax()
    drawdown = cumulative - running_peak
    return float(drawdown.min())


def summarize_trade_performance(trade_analysis: pd.DataFrame) -> dict[str, Any]:
    """Return aggregate performance metrics for already analyzed closed trades."""
    if trade_analysis is None or trade_analysis.empty:
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "flats": 0,
            "win_rate_pct": None,
            "total_realized_pnl": 0.0,
            "avg_pnl": None,
            "avg_winner": None,
            "avg_loser": None,
            "avg_return_pct": None,
            "avg_realized_r_multiple": None,
            "avg_holding_days": None,
            "largest_winner": None,
            "largest_loser": None,
            "profit_factor": None,
            "max_drawdown_pnl": 0.0,
        }

    pnl = pd.to_numeric(trade_analysis.get("realized_pnl"), errors="coerce")
    returns = pd.to_numeric(trade_analysis.get("return_pct"), errors="coerce")
    r_mult = pd.to_numeric(trade_analysis.get("realized_r_multiple"), errors="coerce")
    holding = pd.to_numeric(trade_analysis.get("holding_days"), errors="coerce")

    outcomes = trade_analysis.get("outcome", pd.Series(index=trade_analysis.index, dtype="object"))
    wins = int((outcomes == "WIN").sum())
    losses = int((outcomes == "LOSS").sum())
    flats = int((outcomes == "FLAT").sum())
    total = int(len(trade_analysis))

    positive_pnl = pnl[pnl > 0].sum(min_count=1)
    negative_pnl = pnl[pnl < 0].sum(min_count=1)

    profit_factor = None
    if pd.notna(negative_pnl) and float(negative_pnl) != 0:
        profit_factor = float(positive_pnl) / abs(float(negative_pnl)) if pd.notna(positive_pnl) else 0.0

    return {
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "flats": flats,
        "win_rate_pct": (wins / total * 100.0) if total else None,
        "total_realized_pnl": float(pnl.sum(min_count=1)) if pnl.notna().any() else 0.0,
        "avg_pnl": _safe_float(pnl.mean()),
        "avg_winner": _safe_float(pnl[pnl > 0].mean()),
        "avg_loser": _safe_float(pnl[pnl < 0].mean()),
        "avg_return_pct": _safe_float(returns.mean()),
        "avg_realized_r_multiple": _safe_float(r_mult.mean()),
        "avg_holding_days": _safe_float(holding.mean()),
        "largest_winner": _safe_float(pnl.max()),
        "largest_loser": _safe_float(pnl.min()),
        "profit_factor": profit_factor,
        "max_drawdown_pnl": _max_drawdown_from_pnl(pnl.dropna()),
    }


def build_signal_component_report(trade_analysis: pd.DataFrame) -> pd.DataFrame:
    """Compare average signal components across WIN/LOSS/FLAT outcomes."""
    if trade_analysis is None or trade_analysis.empty:
        return pd.DataFrame(
            columns=["outcome", "trade_count", *SIGNAL_SCORE_FIELDS]
        )

    rows: list[dict[str, Any]] = []
    for outcome in ["WIN", "LOSS", "FLAT"]:
        subset = trade_analysis[trade_analysis["outcome"] == outcome]
        if subset.empty:
            continue

        row: dict[str, Any] = {
            "outcome": outcome,
            "trade_count": int(len(subset)),
        }
        for field in SIGNAL_SCORE_FIELDS:
            row[field] = _safe_float(
                pd.to_numeric(subset[field], errors="coerce").mean()
            ) if field in subset.columns else None
        rows.append(row)

    return pd.DataFrame(rows)


def build_signal_summary(trade_analysis: pd.DataFrame) -> pd.DataFrame:
    """Return a long-form summary of signal components by outcome."""
    component_report = build_signal_component_report(trade_analysis)
    if component_report.empty:
        return pd.DataFrame(columns=["signal", "outcome", "trade_count", "mean_score"])

    rows: list[dict[str, Any]] = []
    for _, row in component_report.iterrows():
        for field in SIGNAL_SCORE_FIELDS:
            rows.append(
                {
                    "signal": field,
                    "outcome": row["outcome"],
                    "trade_count": int(row["trade_count"]),
                    "mean_score": row[field],
                }
            )
    return pd.DataFrame(rows)


def load_trade_report(
    db_path: str = "data/stock_scout.db",
    portfolio_id: str = "default",
) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame]:
    """Load closed trades and return detail rows, performance metrics, and signal stats."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    trade_analysis = load_closed_trade_analysis(
        db_path=db_path,
        portfolio_id=portfolio_id,
    )
    metrics = summarize_trade_performance(trade_analysis)
    signal_report = build_signal_component_report(trade_analysis)
    return trade_analysis, metrics, signal_report
