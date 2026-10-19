from __future__ import annotations

import argparse
from datetime import datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf


def _now_local(timezone_name: str) -> datetime:
    return datetime.now(ZoneInfo(timezone_name))


def _in_entry_window(now: datetime) -> bool:
    """Allow new paper entries during the delayed US opening window."""
    if now.weekday() >= 5:
        return False

    # GitHub Actions scheduled workflows can start later than their
    # scheduled time. Allow delayed execution through 10:30 ET.
    return time(9, 30) <= now.time() < time(10, 30)


def get_opening_window_prices(
    tickers: list[str],
    timezone_name: str = "America/New_York",
    interval: str = "5m",
    period: str = "1d",
) -> tuple[dict[str, float], dict[str, str]]:
    """Get the latest available regular-session 5-minute price.

    This is paper trading, not a broker execution feed. The value used for
    the simulated entry is the latest available regular-session intraday
    close returned by Yahoo Finance in the opening window.
    """
    prices: dict[str, float] = {}
    timestamps: dict[str, str] = {}
    timezone = ZoneInfo(timezone_name)

    for ticker in tickers:
        try:
            frame = yf.Ticker(ticker).history(
                period=period,
                interval=interval,
                prepost=False,
                auto_adjust=False,
            )
        except Exception as exc:
            print(f"PRICE_FETCH_ERROR {ticker}: {exc}")
            continue

        if frame.empty:
            print(f"PRICE_FETCH_EMPTY {ticker}")
            continue

        index = pd.DatetimeIndex(frame.index)
        if index.tz is None:
            index = index.tz_localize("UTC")

        frame = frame.copy()
        frame.index = index.tz_convert(timezone)
        frame = frame.sort_index()

        # Use the latest available regular-session 5-minute price
        # from the market open up to the actual workflow execution time.
        current_time = _now_local(timezone_name)
        
        regular = frame[
        (frame.index.time >= time(9, 30))
         & (frame.index.time <= current_time.time())
        ]

        if regular.empty:
        print(f"PRICE_FETCH_NO_OPENING_WINDOW {ticker}")
        continue

        price = float(regular["Close"].iloc[-1])
        if not pd.notna(price) or price <= 0:
            print(f"PRICE_FETCH_INVALID {ticker}")
            continue

        timestamp = regular.index[-1].isoformat()
        prices[ticker] = price
        timestamps[ticker] = timestamp

        print(f"OPENING_PRICE {ticker} {price:.4f} {timestamp}")

    return prices, timestamps


def run_once(config_path: str = "config/config.yaml") -> dict[str, Any]:
    from agents.scanner import run_scan
    from agents.technical import analyze_candidates
    from database.db import ensure_portfolio_schema
    from main import load_config, persist_selection
    from portfolio.paper_trading import PaperPortfolio
    from scoring.signal_engine import rank_top10

    cfg = load_config(config_path)
    timezone_name = cfg["intraday"]["timezone"]
    now = _now_local(timezone_name)

    # Hard safety guard: a manual workflow_dispatch outside this window
    # cannot accidentally open positions.
    if not _in_entry_window(now):
        print(
            "Morning entry skipped: "
            f"outside opening window ({now.isoformat()})."
        )
        return {
            "config_path": str(Path(config_path)),
            "scanned": 0,
            "top10": 0,
            "entry_prices": {},
            "open_positions": 0,
            "snapshot": None,
            "skipped": True,
        }

    db_path = cfg["database"]["path"]
    ensure_portfolio_schema(db_path)

    scan, history = run_scan(
        source_url=cfg["market"]["sp500_source_url"],
        min_price=cfg["scanner"]["min_price"],
        min_avg_dollar_volume_20d=cfg["scanner"]["min_avg_dollar_volume_20d"],
        period=cfg["market"]["history_period"],
        interval=cfg["market"]["interval"],
        batch_size=cfg["scanner"]["batch_size"],
        max_symbols=cfg["scanner"]["max_symbols"],
    )

    technical = analyze_candidates(scan, history, **cfg["technical"])
    top10 = rank_top10(technical, cfg["portfolio"]["positions"])

    portfolio = PaperPortfolio(
        db_path=db_path,
        starting_cash=cfg["portfolio"]["starting_cash"],
        max_positions=cfg["portfolio"]["positions"],
    )

    current_open = portfolio.open_positions()
    available_slots = max(
        0,
        cfg["portfolio"]["positions"] - len(current_open),
    )

    if available_slots <= 0:
        print("Morning entry skipped: portfolio is full.")
        snapshot = portfolio.snapshot()
        portfolio_status = portfolio.status()
        persist_selection(
            scan,
            technical,
            top10,
            db_path,
            portfolio_status,
        )
        return {
            "config_path": str(Path(config_path)),
            "scanned": len(scan),
            "top10": len(top10),
            "entry_prices": {},
            "open_positions": len(current_open),
            "snapshot": snapshot,
            "skipped": True,
        }

    if top10.empty:
        print("Morning entry skipped: no candidates.")
        snapshot = portfolio.snapshot()
        portfolio_status = portfolio.status()
        persist_selection(
            scan,
            technical,
            top10,
            db_path,
            portfolio_status,
        )
        return {
            "config_path": str(Path(config_path)),
            "scanned": len(scan),
            "top10": 0,
            "entry_prices": {},
            "open_positions": len(current_open),
            "snapshot": snapshot,
            "skipped": True,
        }

    candidate_tickers = top10["ticker"].astype(str).tolist()

    entry_prices, entry_timestamps = get_opening_window_prices(
        candidate_tickers,
        timezone_name=timezone_name,
        interval=cfg["intraday"]["interval"],
        period=cfg["intraday"]["period"],
    )

    if not entry_prices:
        print("Morning entry skipped: no opening prices available.")
        snapshot = portfolio.snapshot()
        portfolio_status = portfolio.status()
        persist_selection(
            scan,
            technical,
            top10,
            db_path,
            portfolio_status,
        )
        return {
            "config_path": str(Path(config_path)),
            "scanned": len(scan),
            "top10": len(top10),
            "entry_prices": {},
            "open_positions": len(current_open),
            "snapshot": snapshot,
            "skipped": True,
        }

    # Keep only candidates for which a current regular-session price exists.
    execution_top10 = top10[
        top10["ticker"].astype(str).isin(entry_prices.keys())
    ].copy()

    # Rebuild the execution plan from the opening-window price.
    for idx, row in execution_top10.iterrows():
        ticker = str(row["ticker"])
        entry = float(entry_prices[ticker])
        atr = float(row["atr14"])

        execution_top10.at[idx, "entry"] = entry
        execution_top10.at[idx, "stop"] = (
            entry
            - float(cfg["technical"]["stop_atr_multiple"]) * atr
        )
        execution_top10.at[idx, "target"] = (
            entry
            + float(cfg["technical"]["target_atr_multiple"]) * atr
        )
        execution_top10.at[idx, "entry_source"] = "OPENING_WINDOW_INTRADAY"
        execution_top10.at[idx, "entry_reference_time"] = entry_timestamps.get(ticker)

    # sync_from_top10 only fills free slots and never replaces OPEN positions.
    open_positions = portfolio.sync_from_top10(
        execution_top10,
        trade_reason="OPENING_ENTRY",
    )

    latest_prices = {
        ticker: float(frame["Close"].iloc[-1])
        for ticker, frame in history.items()
        if not frame.empty
    }
    latest_prices.update(entry_prices)

    snapshot = portfolio.snapshot(latest_prices)
    portfolio_status = portfolio.status(latest_prices)

    persist_selection(
        scan,
        technical,
        top10,
        db_path,
        portfolio_status,
    )

    print("STOCK SCOUT AI — MORNING ENTRY CYCLE")
    print(f"Scanned: {len(scan)} symbols")
    print(f"Top 10 candidates: {len(top10)}")
    print(f"Opening prices available: {len(entry_prices)}")
    print(f"Open positions: {len(open_positions)}")
    print(f"Portfolio snapshot: {snapshot}")

    return {
        "config_path": str(Path(config_path)),
        "scanned": len(scan),
        "top10": len(top10),
        "entry_prices": entry_prices,
        "open_positions": len(open_positions),
        "snapshot": snapshot,
        "skipped": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the Stock Scout AI opening-window paper-entry cycle"
    )
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="Path to the YAML configuration file",
    )
    args = parser.parse_args()
    run_once(args.config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
