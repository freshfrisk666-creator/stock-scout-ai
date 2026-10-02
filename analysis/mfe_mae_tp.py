from __future__ import annotations

import math
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd

TP_LEVELS_R = [0.50, 0.75, 1.00, 1.25, 1.50, 2.00, 2.50, 3.00]
BE_TRIGGER_R = 0.75
BE_FINAL_TP_R = 3.00
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
    return out.sort_index().dropna(subset=["High", "Low", "Close"])


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


def _position_risk(row: Any) -> tuple[float, float, float]:
    entry = float(row["entry_price"])
    stop = float(row["stop"])
    risk = abs(entry - stop)
    if risk <= 0:
        raise ValueError("Position risk must be greater than zero")
    return entry, stop, risk


def simulate_exit_policy(
    row: Any,
    tp_r: float,
    bars: pd.DataFrame,
    breakeven_trigger_r: float | None = None,
) -> dict[str, Any]:
    """Simulate a long trade on daily OHLC.

    Stop is fixed at -1R. Optional breakeven trigger is armed when the day's
    High reaches the trigger and becomes effective on the next bar, avoiding
    an intraday ordering assumption from daily OHLC data.
    """
    entry, initial_stop, risk = _position_risk(row)
    bars = normalize_daily_bars(bars)
    if bars.empty:
        return {
            "result": "UNRESOLVED", "realized_r": math.nan,
            "exit_date": None, "bars_observed": 0,
            "breakeven_armed": False,
        }

    target_price = entry + float(tp_r) * risk
    current_stop = initial_stop
    be_armed = False

    for bar_date, bar in bars.iterrows():
        high = float(bar["High"])
        low = float(bar["Low"])
        hit_stop = low <= current_stop
        hit_target = high >= target_price

        if hit_stop and hit_target:
            return {
                "result": "AMBIGUOUS", "realized_r": math.nan,
                "exit_date": bar_date, "bars_observed": len(bars.loc[:bar_date]),
                "breakeven_armed": be_armed,
            }
        if hit_target:
            return {
                "result": "TARGET", "realized_r": float(tp_r),
                "exit_date": bar_date, "bars_observed": len(bars.loc[:bar_date]),
                "breakeven_armed": be_armed,
            }
        if hit_stop:
            stop_r = 0.0 if be_armed else -1.0
            return {
                "result": "BREAKEVEN" if be_armed else "STOP",
                "realized_r": stop_r,
                "exit_date": bar_date, "bars_observed": len(bars.loc[:bar_date]),
                "breakeven_armed": be_armed,
            }

        if (
            breakeven_trigger_r is not None
            and not be_armed
            and high >= entry + float(breakeven_trigger_r) * risk
        ):
            # Effective on the next bar; this is deterministic with daily OHLC.
            be_armed = True
            current_stop = entry

    return {
        "result": "UNRESOLVED", "realized_r": math.nan,
        "exit_date": None, "bars_observed": len(bars),
        "breakeven_armed": be_armed,
    }


def resolve_ambiguous(result: str, tp_r: float, scenario: str) -> tuple[str, float]:
    if result == "AMBIGUOUS":
        if scenario == "conservative":
            return "STOP", -1.0
        if scenario == "optimistic":
            return "TARGET", float(tp_r)
        raise ValueError("scenario must be 'conservative' or 'optimistic'")
    if result in {"TARGET", "STOP", "BREAKEVEN"}:
        return result, {"TARGET": float(tp_r), "STOP": -1.0, "BREAKEVEN": 0.0}[result]
    return "UNRESOLVED", math.nan


def load_positions(db_path: str = "data/stock_scout.db", portfolio_id: str = "default") -> pd.DataFrame:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(
            """
            SELECT id, ticker, rank, entry_date, entry_price, shares, notional,
                   stop, target, status, technical_score, strategy_type,
                   planned_horizon_sessions, exit_date, exit_price, realized_pnl,
                   close_reason
            FROM positions
            WHERE portfolio_id = ?
            ORDER BY id ASC
            """,
            conn,
            params=(portfolio_id,),
        )


def _default_portfolio_marks(portfolio_status: pd.DataFrame | None) -> dict[str, float]:
    if portfolio_status is None or portfolio_status.empty:
        return {}
    if not {"ticker", "mark_price"}.issubset(portfolio_status.columns):
        return {}
    return (
        portfolio_status.dropna(subset=["ticker", "mark_price"])
        .drop_duplicates(subset=["ticker"], keep="last")
        .set_index("ticker")["mark_price"]
        .astype(float)
        .to_dict()
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
        entry, stop, risk = _position_risk(row)
        entry_date = _ny_date(row["entry_date"])
        status_label = str(row["status"]).upper()
        cutoff = _ny_date(row["exit_date"]) if status_label == "CLOSED" and pd.notna(row["exit_date"]) else today_ny
        key = (ticker, entry_date, cutoff)
        if key not in bar_cache:
            bar_cache[key] = downloader(ticker, entry_date, cutoff)
        bars = normalize_daily_bars(bar_cache[key])
        if bars.empty:
            rows.append({"position_id": int(row["id"]), "ticker": ticker, "status": status_label,
                         "entry_date": str(row["entry_date"]), "entry_price": entry, "stop": stop,
                         "target": float(row["target"]), "risk_per_share": risk,
                         "mfe_R": math.nan, "mae_R": math.nan, "current_R": math.nan,
                         "max_high": math.nan, "min_low": math.nan, "bars_observed": 0})
            continue
        max_high = float(bars["High"].max())
        min_low = float(bars["Low"].min())
        mark = float(row["exit_price"]) if status_label == "CLOSED" and pd.notna(row["exit_price"]) else float(portfolio_marks.get(ticker, bars["Close"].iloc[-1]))
        rows.append({"position_id": int(row["id"]), "ticker": ticker, "status": status_label,
                     "entry_date": str(row["entry_date"]), "entry_price": entry, "stop": stop,
                     "target": float(row["target"]), "risk_per_share": risk,
                     "mfe_R": (max_high - entry) / risk, "mae_R": (entry - min_low) / risk,
                     "current_R": (mark - entry) / risk, "max_high": max_high,
                     "min_low": min_low, "bars_observed": int(len(bars))})
    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values(["status", "mfe_R"], ascending=[True, False]).reset_index(drop=True)
    return result, bar_cache


def build_open_tp_sensitivity(mfe_mae: pd.DataFrame) -> pd.DataFrame:
    open_positions = mfe_mae[mfe_mae["status"] == "OPEN"].copy()
    if open_positions.empty:
        return pd.DataFrame(columns=["tp_R", "open_positions", "open_positions_reached_TP_on_path", "pct_open_reached_TP_on_path"])
    rows = []
    for tp_r in TP_LEVELS_R:
        reached = int((open_positions["mfe_R"] >= tp_r).sum())
        rows.append({"tp_R": tp_r, "open_positions": len(open_positions),
                     "open_positions_reached_TP_on_path": reached,
                     "pct_open_reached_TP_on_path": 100.0 * reached / len(open_positions)})
    return pd.DataFrame(rows)


def _summary_from_rows(rows: pd.DataFrame, result_col: str, r_col: str) -> dict[str, Any]:
    values = pd.to_numeric(rows[r_col], errors="coerce")
    valid = values.dropna()
    targets = int((rows[result_col] == "TARGET").sum())
    stops = int((rows[result_col] == "STOP").sum())
    be = int((rows[result_col] == "BREAKEVEN").sum())
    unresolved = int((rows[result_col] == "UNRESOLVED").sum())
    ambiguous = int((rows[result_col] == "AMBIGUOUS").sum())
    wins = int((values > 0).sum())
    losses = int((values < 0).sum())
    gross_profit = float(values[values > 0].sum())
    gross_loss = float(values[values < 0].sum())
    pf = gross_profit / abs(gross_loss) if gross_loss < 0 else math.nan
    return {
        "trades": len(rows), "targets": targets, "stops": stops, "breakevens": be,
        "ambiguous": ambiguous, "unresolved": unresolved, "wins": wins,
        "losses": losses, "win_rate_pct": 100.0 * wins / len(rows) if len(rows) else math.nan,
        "total_R": float(valid.sum()), "avg_R": float(valid.mean()) if not valid.empty else math.nan,
        "profit_factor": pf, "gross_profit_R": gross_profit, "gross_loss_R": gross_loss,
    }


def run_exit_strategy_study(
    positions_all: pd.DataFrame,
    today_ny: pd.Timestamp | None = None,
    downloader: Downloader = download_daily_bars,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run alternate exit policies on every CLOSED position.

    The alternative policy is simulated from entry through today, rather than
    stopping at the original exit date. This lets a higher TP continue past an
    original exit when the alternative rules would have held the position.
    """
    today_ny = today_ny or pd.Timestamp.now(tz="America/New_York").normalize().tz_localize(None)
    closed = positions_all[positions_all["status"].astype(str).str.upper() == "CLOSED"].copy()
    if closed.empty:
        return pd.DataFrame(), pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for _, row in closed.iterrows():
        ticker = str(row["ticker"])
        entry_date = _ny_date(row["entry_date"])
        bars = normalize_daily_bars(downloader(ticker, entry_date, today_ny))
        for tp_r in TP_LEVELS_R:
            base = simulate_exit_policy(row, tp_r, bars)
            cons_result, cons_r = resolve_ambiguous(base["result"], tp_r, "conservative")
            opt_result, opt_r = resolve_ambiguous(base["result"], tp_r, "optimistic")
            rows.append({"position_id": int(row["id"]), "ticker": ticker, "strategy": f"TP_{tp_r:g}R",
                         "tp_R": tp_r, "result": base["result"], "base_R": base["realized_r"],
                         "exit_date": base["exit_date"], "conservative_result": cons_result,
                         "conservative_R": cons_r, "optimistic_result": opt_result, "optimistic_R": opt_r,
                         "breakeven_trigger_R": math.nan})

        be = simulate_exit_policy(row, BE_FINAL_TP_R, bars, breakeven_trigger_r=BE_TRIGGER_R)
        cons_result, cons_r = resolve_ambiguous(be["result"], BE_FINAL_TP_R, "conservative")
        opt_result, opt_r = resolve_ambiguous(be["result"], BE_FINAL_TP_R, "optimistic")
        rows.append({"position_id": int(row["id"]), "ticker": ticker,
                     "strategy": f"BE_{BE_TRIGGER_R:g}R_THEN_TP_{BE_FINAL_TP_R:g}R",
                     "tp_R": BE_FINAL_TP_R, "result": be["result"], "base_R": be["realized_r"],
                     "exit_date": be["exit_date"], "conservative_result": cons_result,
                     "conservative_R": cons_r, "optimistic_result": opt_result, "optimistic_R": opt_r,
                     "breakeven_trigger_R": BE_TRIGGER_R})

    by_trade = pd.DataFrame(rows)
    summary_rows: list[dict[str, Any]] = []
    for strategy, subset in by_trade.groupby("strategy", sort=False):
        summary_rows.append({"strategy": strategy, **_summary_from_rows(subset, "conservative_result", "conservative_R"),
                             "optimistic_win_rate_pct": _summary_from_rows(subset, "optimistic_result", "optimistic_R")["win_rate_pct"],
                             "optimistic_total_R": _summary_from_rows(subset, "optimistic_result", "optimistic_R")["total_R"],
                             "optimistic_avg_R": _summary_from_rows(subset, "optimistic_result", "optimistic_R")["avg_R"]})
    return pd.DataFrame(by_trade), pd.DataFrame(summary_rows)


def run_analysis(
    db_path: str = "data/stock_scout.db",
    portfolio_id: str = "default",
    portfolio_status: pd.DataFrame | None = None,
    today_ny: pd.Timestamp | None = None,
    downloader: Downloader = download_daily_bars,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    positions = load_positions(db_path, portfolio_id)
    marks = _default_portfolio_marks(portfolio_status)
    mfe_mae, _ = build_mfe_mae_analysis(positions, marks, today_ny, downloader)
    open_sensitivity = build_open_tp_sensitivity(mfe_mae)
    tp_by_trade, tp_summary = run_exit_strategy_study(positions, today_ny, downloader)
    return mfe_mae, tp_by_trade, tp_summary, open_sensitivity
