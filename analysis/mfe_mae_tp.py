from __future__ import annotations

import math
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd


TP_LEVELS_R = [0.50, 0.75, 1.00, 1.25, 1.50, 2.00, 2.50, 3.00]
REQUIRED_OHLC = ["High", "Low", "Close"]
Downloader = Callable[[str, pd.Timestamp, pd.Timestamp], pd.DataFrame]


def _ny_date(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, utc=True)
    return ts.tz_convert("America/New_York").normalize().tz_localize(None)


def normalize_daily_bars(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = out.columns.get_level_values(0)

    missing = [c for c in REQUIRED_OHLC if c not in out.columns]
    if missing:
        raise ValueError(f"Missing required OHLC columns: {missing}")

    out = out[REQUIRED_OHLC].copy()
    idx = pd.DatetimeIndex(pd.to_datetime(out.index))
    if idx.tz is not None:
        idx = idx.tz_convert("America/New_York").tz_localize(None)
    out.index = idx
    out = out.sort_index()
    return out.dropna(subset=["High", "Low", "Close"])


def download_daily_bars(
    ticker: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
    if start_date is None or end_date is None or start_date > end_date:
        return pd.DataFrame()

    import yfinance as yf

    df = yf.download(
        ticker,
        start=start_date.strftime("%Y-%m-%d"),
        end=(end_date + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
        interval="1d",
        auto_adjust=False,
        progress=False,
    )
    return normalize_daily_bars(df)


def simulate_tp_for_trade(
    row: Any,
    tp_r: float,
    bars: pd.DataFrame,
) -> tuple[str, float, pd.Timestamp | None]:
    """Simulate a long trade with fixed -1R stop and +tp_r target."""
    entry = float(row["entry_price"])
    stop = float(row["stop"])
    risk = abs(entry - stop)
    if risk <= 0 or bars.empty:
        return "UNRESOLVED", math.nan, None

    target_price = entry + float(tp_r) * risk

    for bar_date, bar in normalize_daily_bars(bars).iterrows():
        high = float(bar["High"])
        low = float(bar["Low"])
        hit_stop = low <= stop
        hit_target = high >= target_price

        if hit_stop and hit_target:
            return "AMBIGUOUS", math.nan, bar_date
        if hit_target:
            return "TARGET", float(tp_r), bar_date
        if hit_stop:
            return "STOP", -1.0, bar_date

    return "UNRESOLVED", math.nan, None


def resolve_ambiguous(
    result: str,
    tp_r: float,
    scenario: str,
) -> tuple[str, float]:
    if result != "AMBIGUOUS":
        if result == "TARGET":
            return "TARGET", float(tp_r)
        if result == "STOP":
            return "STOP", -1.0
        return "UNRESOLVED", math.nan

    if scenario == "conservative":
        return "STOP", -1.0
    if scenario == "optimistic":
        return "TARGET", float(tp_r)
    raise ValueError("scenario must be 'conservative' or 'optimistic'")


def _default_portfolio_marks(portfolio_status: pd.DataFrame | None) -> dict[str, float]:
    if portfolio_status is None or portfolio_status.empty:
        return {}
    required = {"ticker", "mark_price"}
    if not required.issubset(portfolio_status.columns):
        return {}
    return (
        portfolio_status.dropna(subset=["ticker", "mark_price"])
        .drop_duplicates(subset=["ticker"], keep="last")
        .set_index("ticker")["mark_price"]
        .astype(float)
        .to_dict()
    )


def load_positions(
    db_path: str = "data/stock_scout.db",
    portfolio_id: str = "default",
) -> pd.DataFrame:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(
            """
            SELECT
                id, ticker, rank, entry_date, entry_price, shares,
                notional, stop, target, status, technical_score,
                strategy_type, planned_horizon_sessions,
                exit_date, exit_price, realized_pnl, close_reason
            FROM positions
            WHERE portfolio_id = ?
            ORDER BY id ASC
            """,
            conn,
            params=(portfolio_id,),
        )


def build_mfe_mae_analysis(
    positions_all: pd.DataFrame,
    portfolio_marks: dict[str, float] | None = None,
    today_ny: pd.Timestamp | None = None,
    downloader: Downloader = download_daily_bars,
) -> tuple[pd.DataFrame, dict[tuple[str, pd.Timestamp, pd.Timestamp], pd.DataFrame]]:
    portfolio_marks = portfolio_marks or {}
    today_ny = today_ny or pd.Timestamp.now(tz="America/New_York").normalize().tz_localize(None)

    rows: list[dict[str, Any]] = []
    bar_cache: dict[tuple[str, pd.Timestamp, pd.Timestamp], pd.DataFrame] = {}

    for _, row in positions_all.iterrows():
        ticker = str(row["ticker"])
        entry = float(row["entry_price"])
        stop = float(row["stop"])
        risk = abs(entry - stop)
        if risk <= 0:
            continue

        entry_date = _ny_date(row["entry_date"])
        status_label = str(row["status"]).upper()
        if status_label == "CLOSED" and pd.notna(row["exit_date"]):
            cutoff_date = _ny_date(row["exit_date"])
        else:
            cutoff_date = today_ny
            status_label = "OPEN"

        cache_key = (ticker, entry_date, cutoff_date)
        if cache_key not in bar_cache:
            bar_cache[cache_key] = downloader(ticker, entry_date, cutoff_date)
        bars = normalize_daily_bars(bar_cache[cache_key])

        if bars.empty:
            rows.append({
                "position_id": int(row["id"]),
                "ticker": ticker,
                "status": status_label,
                "entry_date": str(row["entry_date"]),
                "entry_price": entry,
                "stop": stop,
                "target": float(row["target"]),
                "risk_per_share": risk,
                "mfe_R": math.nan,
                "mae_R": math.nan,
                "current_R": math.nan,
                "max_high": math.nan,
                "min_low": math.nan,
                "bars_observed": 0,
            })
            continue

        max_high = float(bars["High"].max())
        min_low = float(bars["Low"].min())
        mfe_r = (max_high - entry) / risk
        mae_r = (entry - min_low) / risk

        if status_label == "CLOSED" and pd.notna(row["exit_price"]):
            mark = float(row["exit_price"])
        else:
            mark = float(portfolio_marks.get(ticker, bars["Close"].iloc[-1]))

        rows.append({
            "position_id": int(row["id"]),
            "ticker": ticker,
            "status": status_label,
            "entry_date": str(row["entry_date"]),
            "entry_price": entry,
            "stop": stop,
            "target": float(row["target"]),
            "risk_per_share": risk,
            "mfe_R": mfe_r,
            "mae_R": mae_r,
            "current_R": (mark - entry) / risk,
            "max_high": max_high,
            "min_low": min_low,
            "bars_observed": int(len(bars)),
        })

    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values(["status", "mfe_R"], ascending=[True, False]).reset_index(drop=True)
    return result, bar_cache


def simulate_take_profit(
    positions_all: pd.DataFrame,
    bar_cache: dict[tuple[str, pd.Timestamp, pd.Timestamp], pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    closed_positions = positions_all[positions_all["status"].astype(str).str.upper() == "CLOSED"].copy()
    simulation_rows: list[dict[str, Any]] = []

    for _, row in closed_positions.iterrows():
        ticker = str(row["ticker"])
        entry_date = _ny_date(row["entry_date"])
        exit_date = _ny_date(row["exit_date"]) if pd.notna(row["exit_date"]) else entry_date
        bars = bar_cache.get((ticker, entry_date, exit_date), pd.DataFrame())
        for tp_r in TP_LEVELS_R:
            base_result, base_r, base_date = simulate_tp_for_trade(row, tp_r, bars)
            conservative_result, conservative_r = resolve_ambiguous(base_result, tp_r, "conservative")
            optimistic_result, optimistic_r = resolve_ambiguous(base_result, tp_r, "optimistic")
            simulation_rows.append({
                "position_id": int(row["id"]),
                "ticker": ticker,
                "tp_R": tp_r,
                "base_result": base_result,
                "base_R": base_r,
                "base_date": str(base_date) if base_date is not None else None,
                "conservative_result": conservative_result,
                "conservative_R": conservative_r,
                "optimistic_result": optimistic_result,
                "optimistic_R": optimistic_r,
            })

    tp_simulation = pd.DataFrame(simulation_rows)
    if tp_simulation.empty:
        return tp_simulation, pd.DataFrame(), pd.DataFrame()

    summary_rows: list[dict[str, Any]] = []
    n = len(closed_positions)
    for tp_r in TP_LEVELS_R:
        subset = tp_simulation[tp_simulation["tp_R"] == tp_r]
        conservative = subset["conservative_R"].dropna()
        optimistic = subset["optimistic_R"].dropna()
        summary_rows.append({
            "tp_R": tp_r,
            "target_price_formula": f"entry + {tp_r}R",
            "conservative_targets": int((subset["conservative_result"] == "TARGET").sum()),
            "conservative_stops": int((subset["conservative_result"] == "STOP").sum()),
            "ambiguous_bars": int((subset["base_result"] == "AMBIGUOUS").sum()),
            "unresolved": int((subset["conservative_result"] == "UNRESOLVED").sum()),
            "conservative_win_rate_pct": 100.0 * (subset["conservative_result"] == "TARGET").sum() / n if n else math.nan,
            "conservative_total_R": conservative.sum(),
            "conservative_avg_R": conservative.mean(),
            "optimistic_targets": int((subset["optimistic_result"] == "TARGET").sum()),
            "optimistic_stops": int((subset["optimistic_result"] == "STOP").sum()),
            "optimistic_win_rate_pct": 100.0 * (subset["optimistic_result"] == "TARGET").sum() / n if n else math.nan,
            "optimistic_total_R": optimistic.sum(),
            "optimistic_avg_R": optimistic.mean(),
        })

    tp_summary = pd.DataFrame(summary_rows)

    open_positions_mfe = None
    return tp_simulation, tp_summary, open_positions_mfe


def build_open_tp_sensitivity(
    mfe_mae: pd.DataFrame,
) -> pd.DataFrame:
    open_positions = mfe_mae[mfe_mae["status"] == "OPEN"].copy()
    if open_positions.empty:
        return pd.DataFrame(columns=[
            "tp_R", "open_positions",
            "open_positions_reached_TP_on_path",
            "pct_open_reached_TP_on_path",
        ])

    rows = []
    for tp_r in TP_LEVELS_R:
        reached = int((open_positions["mfe_R"] >= tp_r).sum())
        rows.append({
            "tp_R": tp_r,
            "open_positions": len(open_positions),
            "open_positions_reached_TP_on_path": reached,
            "pct_open_reached_TP_on_path": 100.0 * reached / len(open_positions),
        })
    return pd.DataFrame(rows)


def run_analysis(
    db_path: str = "data/stock_scout.db",
    portfolio_id: str = "default",
    portfolio_status: pd.DataFrame | None = None,
    today_ny: pd.Timestamp | None = None,
    downloader: Downloader = download_daily_bars,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    positions = load_positions(db_path, portfolio_id)
    marks = _default_portfolio_marks(portfolio_status)
    mfe_mae, bar_cache = build_mfe_mae_analysis(
        positions,
        portfolio_marks=marks,
        today_ny=today_ny,
        downloader=downloader,
    )
    tp_simulation, tp_summary, _ = simulate_take_profit(positions, bar_cache)
    open_sensitivity = build_open_tp_sensitivity(mfe_mae)
    return mfe_mae, tp_simulation, tp_summary, open_sensitivity
