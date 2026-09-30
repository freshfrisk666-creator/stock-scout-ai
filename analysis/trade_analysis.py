from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pandas as pd


SIGNAL_FIELDS = [
    "technical_score",
    "trend_score",
    "momentum_score",
    "rsi_score",
    "volume_score",
    "breakout_score",
]


def parse_signal_snapshot(raw_snapshot: Any) -> dict[str, Any]:
    """Decode a stored signal snapshot. Missing/invalid snapshots become {}."""
    if raw_snapshot is None:
        return {}
    if isinstance(raw_snapshot, Mapping):
        return dict(raw_snapshot)
    if isinstance(raw_snapshot, str):
        try:
            value = json.loads(raw_snapshot)
        except json.JSONDecodeError:
            return {}
        return dict(value) if isinstance(value, dict) else {}
    return {}


def _to_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _score_label(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score >= 80:
        return "strong"
    if score >= 60:
        return "moderate"
    return "weak"


def _signal_profile(snapshot: Mapping[str, Any]) -> str:
    labels: list[str] = []

    trend = _to_float(snapshot.get("trend_score"))
    momentum = _to_float(snapshot.get("momentum_score"))
    rsi = _to_float(snapshot.get("rsi_score"))
    volume = _to_float(snapshot.get("volume_score"))
    breakout = _to_float(snapshot.get("breakout_score"))

    for name, score in (
        ("trend", trend),
        ("momentum", momentum),
        ("RSI", rsi),
        ("volume", volume),
        ("breakout", breakout),
    ):
        if score is not None:
            labels.append(f"{name} {_score_label(score)} ({score:.1f})")

    return "; ".join(labels) if labels else "no scored signal fields available"


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = pd.to_datetime(value, utc=True)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def _holding_days(entry_date: Any, exit_date: Any) -> float | None:
    entry = _parse_dt(entry_date)
    exit_ = _parse_dt(exit_date)
    if entry is None or exit_ is None:
        return None
    return (exit_ - entry).total_seconds() / 86400.0


def _outcome(realized_pnl: float | None) -> str:
    if realized_pnl is None:
        return "UNKNOWN"
    if realized_pnl > 0:
        return "WIN"
    if realized_pnl < 0:
        return "LOSS"
    return "FLAT"


def analyze_closed_trade(trade: Mapping[str, Any] | pd.Series) -> dict[str, Any]:
    """Create a deterministic post-trade explanation from a closed position."""
    row = dict(trade)
    snapshot = parse_signal_snapshot(row.get("signal_snapshot"))

    entry_price = _to_float(row.get("entry_price"), _to_float(snapshot.get("entry")))
    exit_price = _to_float(row.get("exit_price"), _to_float(row.get("price")))
    stop = _to_float(row.get("stop"), _to_float(snapshot.get("stop")))
    target = _to_float(row.get("target"), _to_float(snapshot.get("target")))
    shares = int(_to_float(row.get("shares"), 0) or 0)
    realized_pnl = _to_float(row.get("realized_pnl"), 0.0)

    return_pct = None
    if entry_price not in (None, 0) and exit_price is not None:
        return_pct = (exit_price - entry_price) / entry_price * 100.0

    risk_per_share = None
    reward_per_share = None
    realized_r_multiple = None
    if entry_price is not None and stop is not None:
        risk_per_share = entry_price - stop
    if entry_price is not None and target is not None:
        reward_per_share = target - entry_price
    if risk_per_share and realized_pnl is not None and shares:
        realized_r_multiple = realized_pnl / (risk_per_share * shares)

    reason = str(row.get("close_reason") or row.get("reason") or "UNKNOWN")
    outcome = _outcome(realized_pnl)
    rank = _to_float(row.get("rank"), _to_float(snapshot.get("rank")))
    technical_score = _to_float(
        row.get("technical_score"), _to_float(snapshot.get("technical_score"))
    )

    strengths = []
    weaknesses = []
    for field in ("trend_score", "momentum_score", "rsi_score", "volume_score", "breakout_score"):
        value = _to_float(snapshot.get(field))
        if value is None:
            continue
        if value >= 80:
            strengths.append(field.replace("_score", ""))
        elif value < 60:
            weaknesses.append(field.replace("_score", ""))

    if reason == "TARGET_CLOSE":
        exit_observation = "target reached"
    elif reason == "STOP_CLOSE":
        exit_observation = "stop reached"
    else:
        exit_observation = reason.lower().replace("_", " ")

    explanation_parts = [
        f"Outcome: {outcome}; exit: {exit_observation}.",
    ]
    if strengths:
        explanation_parts.append("Strong signal components: " + ", ".join(strengths) + ".")
    if weaknesses:
        explanation_parts.append("Weaker signal components: " + ", ".join(weaknesses) + ".")
    if technical_score is not None:
        explanation_parts.append(f"Technical score at entry: {technical_score:.1f}.")

    explanation_parts.append(
        "This is an observed relationship in the stored signal and trade outcome; "
        "it does not by itself establish causation."
    )

    return {
        "position_id": row.get("position_id", row.get("id")),
        "ticker": row.get("ticker"),
        "outcome": outcome,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "stop": stop,
        "target": target,
        "shares": shares,
        "realized_pnl": realized_pnl,
        "return_pct": return_pct,
        "risk_per_share": risk_per_share,
        "reward_per_share": reward_per_share,
        "realized_r_multiple": realized_r_multiple,
        "close_reason": reason,
        "entry_date": row.get("entry_date"),
        "exit_date": row.get("exit_date", row.get("timestamp")),
        "holding_days": _holding_days(
            row.get("entry_date"),
            row.get("exit_date", row.get("timestamp")),
        ),
        "rank": int(rank) if rank is not None else None,
        "technical_score": technical_score,
        "trend_score": _to_float(snapshot.get("trend_score")),
        "momentum_score": _to_float(snapshot.get("momentum_score")),
        "rsi_score": _to_float(snapshot.get("rsi_score")),
        "volume_score": _to_float(snapshot.get("volume_score")),
        "breakout_score": _to_float(snapshot.get("breakout_score")),
        "signal_profile": _signal_profile(snapshot),
        "signal_strengths": ", ".join(strengths),
        "signal_weaknesses": ", ".join(weaknesses),
        "snapshot_version": snapshot.get("_snapshot_version"),
        "explanation": " ".join(explanation_parts),
    }


def analyze_closed_trades(closed_positions: pd.DataFrame) -> pd.DataFrame:
    """Analyze all supplied closed positions, returning one row per trade."""
    if closed_positions is None or closed_positions.empty:
        return pd.DataFrame(
            columns=[
                "position_id", "ticker", "outcome", "entry_price", "exit_price",
                "stop", "target", "shares", "realized_pnl", "return_pct",
                "risk_per_share", "reward_per_share", "realized_r_multiple",
                "close_reason", "entry_date", "exit_date", "holding_days",
                "rank", "technical_score", "trend_score", "momentum_score",
                "rsi_score", "volume_score", "breakout_score", "signal_profile",
                "signal_strengths", "signal_weaknesses", "snapshot_version",
                "explanation",
            ]
        )

    return pd.DataFrame(
        [analyze_closed_trade(row) for _, row in closed_positions.iterrows()]
    )


def load_closed_trade_analysis(
    db_path: str = "data/stock_scout.db",
    portfolio_id: str = "default",
) -> pd.DataFrame:
    """Load CLOSED positions from SQLite and analyze them."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        closed_positions = pd.read_sql_query(
            """
            SELECT
                id AS position_id,
                portfolio_id,
                ticker,
                rank,
                entry_date,
                entry_price,
                shares,
                notional,
                stop,
                target,
                status,
                technical_score,
                signal_snapshot,
                exit_date,
                exit_price,
                realized_pnl,
                close_reason
            FROM positions
            WHERE portfolio_id = ? AND status = 'CLOSED'
            ORDER BY exit_date ASC, position_id ASC
            """,
            conn,
            params=(portfolio_id,),
        )

    return analyze_closed_trades(closed_positions)
