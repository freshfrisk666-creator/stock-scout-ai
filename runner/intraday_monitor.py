from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from database.db import get_connection, ensure_portfolio_schema


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def is_market_session(
    now: datetime | None = None,
    timezone_name: str = "America/New_York",
    market_open: str = "09:30",
    market_close: str = "16:00",
) -> bool:
    """Return True when the US cash session is active on a weekday.

    Holiday handling is intentionally left to the data source: on a market holiday
    yfinance returns no regular-session bars and the monitor exits without changes.
    """
    now = now or _utc_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    local = now.astimezone(ZoneInfo(timezone_name))
    if local.weekday() >= 5:
        return False

    open_time = time.fromisoformat(market_open)
    close_time = time.fromisoformat(market_close)
    return open_time <= local.time() <= close_time


def _normalize_ticker_frame(data: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Extract one ticker's OHLCV frame from yfinance multi-ticker output."""
    if data.empty:
        return pd.DataFrame()

    if isinstance(data.columns, pd.MultiIndex):
        level0 = list(data.columns.get_level_values(0))
        level1 = list(data.columns.get_level_values(1))

        if ticker in level0:
            frame = data[ticker].copy()
        elif ticker in level1:
            frame = data.xs(ticker, axis=1, level=1).copy()
        else:
            return pd.DataFrame()
    else:
        frame = data.copy()

    frame.columns = [str(col) for col in frame.columns]
    required = {"High", "Low", "Close"}
    if not required.issubset(frame.columns):
        return pd.DataFrame()

    return frame.dropna(subset=["High", "Low", "Close"])


def extract_latest_bars(data: pd.DataFrame, tickers: list[str]) -> dict[str, dict[str, Any]]:
    """Return the latest OHLC bar for each requested ticker."""
    result: dict[str, dict[str, Any]] = {}

    for ticker in tickers:
        frame = _normalize_ticker_frame(data, ticker)
        if frame.empty:
            continue

        latest = frame.iloc[-1]
        bar_time = frame.index[-1]
        result[ticker] = {
            "timestamp": bar_time.isoformat() if hasattr(bar_time, "isoformat") else str(bar_time),
            "open": float(latest["Open"]) if "Open" in frame.columns and pd.notna(latest["Open"]) else None,
            "high": float(latest["High"]),
            "low": float(latest["Low"]),
            "close": float(latest["Close"]),
            "volume": float(latest["Volume"]) if "Volume" in frame.columns and pd.notna(latest["Volume"]) else None,
        }

    return result


def fetch_intraday_bars(
    tickers: list[str],
    interval: str = "5m",
    period: str = "1d",
) -> dict[str, dict[str, Any]]:
    """Fetch recent intraday bars for open positions only."""
    if not tickers:
        return {}

    import yfinance as yf

    data = yf.download(
        tickers=tickers,
        period=period,
        interval=interval,
        prepost=False,
        auto_adjust=False,
        group_by="ticker",
        progress=False,
        threads=False,
    )

    if data is None or data.empty:
        return {}

    return extract_latest_bars(data, tickers)


def _bar_is_fresh(
    bar: dict[str, Any],
    reference_time: datetime,
    max_age_minutes: int,
) -> bool:
    raw = bar.get("timestamp")
    if raw is None:
        return False
    try:
        bar_time = pd.to_datetime(raw, utc=True).to_pydatetime()
    except (TypeError, ValueError):
        return False
    age_minutes = (reference_time - bar_time).total_seconds() / 60.0
    return age_minutes <= float(max_age_minutes)


def evaluate_intraday_exits(
    db_path: str,
    bars: dict[str, dict[str, Any]],
    as_of: str | None = None,
    portfolio_id: str = "default",
    max_bar_age_minutes: int = 20,
) -> list[dict[str, Any]]:
    """Close positions whose latest bar touched stop/target.

    If a single bar touches both stop and target, STOP wins because intrabar
    sequencing is unknown; this avoids an optimistic fill assumption.
    """
    ensure_portfolio_schema(db_path)
    as_of = as_of or _utc_now().isoformat()
    reference_time = pd.to_datetime(as_of, utc=True).to_pydatetime()
    closed: list[dict[str, Any]] = []

    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, ticker, shares, entry_price, stop, target, signal_snapshot
            FROM positions
            WHERE portfolio_id = ? AND status = 'OPEN'
            ORDER BY id
            """,
            (portfolio_id,),
        ).fetchall()

        cash_row = conn.execute(
            "SELECT cash FROM portfolio_state WHERE portfolio_id = ?",
            (portfolio_id,),
        ).fetchone()
        if cash_row is None:
            return closed
        cash = float(cash_row[0])

        for row in rows:
            position_id, ticker, shares, entry_price, stop, target, signal_snapshot = row
            bar = bars.get(str(ticker))
            if not bar or not _bar_is_fresh(bar, reference_time, max_bar_age_minutes):
                continue

            high = float(bar["high"])
            low = float(bar["low"])
            exit_price = None
            reason = None

            if low <= float(stop):
                exit_price = float(stop)
                reason = "STOP_CLOSE"
            elif high >= float(target):
                exit_price = float(target)
                reason = "TARGET_CLOSE"

            if exit_price is None:
                continue

            realized_pnl = (exit_price - float(entry_price)) * int(shares)
            notional = exit_price * int(shares)
            cash += notional

            conn.execute(
                """
                UPDATE positions
                SET status = 'CLOSED',
                    exit_date = ?,
                    exit_price = ?,
                    realized_pnl = ?,
                    close_reason = ?
                WHERE id = ?
                """,
                (as_of, exit_price, realized_pnl, reason, position_id),
            )

            conn.execute(
                """
                INSERT INTO trades(
                    portfolio_id, position_id, ticker, side, timestamp,
                    price, shares, notional, cash_after, reason,
                    realized_pnl, signal_snapshot
                ) VALUES (?, ?, ?, 'SELL', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    portfolio_id,
                    position_id,
                    ticker,
                    as_of,
                    exit_price,
                    int(shares),
                    notional,
                    cash,
                    reason,
                    realized_pnl,
                    signal_snapshot,
                ),
            )

            closed.append(
                {
                    "position_id": position_id,
                    "ticker": ticker,
                    "exit_price": exit_price,
                    "shares": int(shares),
                    "realized_pnl": realized_pnl,
                    "reason": reason,
                    "signal_snapshot": signal_snapshot,
                    "bar_timestamp": bar.get("timestamp"),
                    "bar_high": high,
                    "bar_low": low,
                }
            )

        if closed:
            conn.execute(
                """
                UPDATE portfolio_state
                SET cash = ?, updated_at = ?
                WHERE portfolio_id = ?
                """,
                (cash, as_of, portfolio_id),
            )
            conn.commit()

    return closed


def run_monitor_once(
    config_path: str = "config/config.yaml",
    force: bool = False,
) -> dict[str, Any]:
    """Run one intraday-monitor cycle without rescanning the S&P 500."""
    import yaml
    from portfolio.paper_trading import PaperPortfolio

    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    intraday_cfg = cfg.get("intraday", {})
    db_path = cfg["database"]["path"]
    timezone_name = intraday_cfg.get("timezone", "America/New_York")
    market_open = intraday_cfg.get("market_open", "09:30")
    market_close = intraday_cfg.get("market_close", "16:00")
    interval = intraday_cfg.get("interval", "5m")
    period = intraday_cfg.get("period", "1d")
    max_age = int(intraday_cfg.get("max_bar_age_minutes", 20))

    now = _utc_now()
    in_session = is_market_session(
        now,
        timezone_name=timezone_name,
        market_open=market_open,
        market_close=market_close,
    )
    if not in_session and not force:
        return {
            "status": "OUTSIDE_MARKET_SESSION",
            "open_positions": 0,
            "bars": 0,
            "closed": [],
        }

    portfolio = PaperPortfolio(
        db_path=db_path,
        starting_cash=cfg["portfolio"]["starting_cash"],
        max_positions=cfg["portfolio"]["positions"],
    )
    open_positions = portfolio.open_positions()
    tickers = open_positions["ticker"].astype(str).tolist() if not open_positions.empty else []

    if not tickers:
        return {
            "status": "NO_OPEN_POSITIONS",
            "open_positions": 0,
            "bars": 0,
            "closed": [],
        }

    bars = fetch_intraday_bars(tickers, interval=interval, period=period)
    closed = evaluate_intraday_exits(
        db_path=db_path,
        bars=bars,
        as_of=now.isoformat(),
        portfolio_id=portfolio.portfolio_id,
        max_bar_age_minutes=max_age,
    )

    return {
        "status": "OK",
        "open_positions": len(tickers),
        "bars": len(bars),
        "closed": closed,
        "interval": interval,
        "timestamp": now.isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor open paper positions intraday")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run even when outside configured US cash-market hours",
    )
    args = parser.parse_args()

    result = run_monitor_once(args.config, force=args.force)

    print("STOCK SCOUT AI — INTRADAY PAPER MONITOR")
    print(f"Status: {result['status']}")
    print(f"Open positions: {result.get('open_positions', 0)}")
    print(f"Bars fetched: {result.get('bars', 0)}")
    print(f"Closed this cycle: {len(result.get('closed', []))}")

    for trade in result.get("closed", []):
        print(
            f"CLOSED {trade['ticker']} {trade['reason']} "
            f"at {trade['exit_price']:.4f} P&L={trade['realized_pnl']:.2f}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
