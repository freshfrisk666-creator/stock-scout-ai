from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf


DB_PATH = "data/stock_scout.db"
OUTPUT = "dashboard/data.json"


def clean(v):
    if v is None:
        return None

    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass

    if hasattr(v, "item"):
        try:
            v = v.item()
        except (AttributeError, ValueError):
            pass

    if isinstance(v, float) and not math.isfinite(v):
        return None

    return v


def signal(raw):
    """
    Extract the technical values stored in signal_snapshot.
    """
    if not raw:
        return {}

    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}

    keys = [
        "technical_score",
        "trend_score",
        "momentum_score",
        "rsi_score",
        "volume_score",
        "breakout_score",
        "risk_reward",
    ]

    return {
        key: clean(data.get(key))
        for key in keys
        if key in data
    }


def prices(tickers):
    if not tickers:
        return {}

    data = yf.download(
        tickers=tickers,
        period="1d",
        interval="1m",
        prepost=False,
        auto_adjust=False,
        group_by="ticker",
        progress=False,
        threads=False,
    )

    if data is None or data.empty:
        return {}

    out = {}

    for ticker in tickers:
        try:
            if isinstance(data.columns, pd.MultiIndex):
                if ticker in data.columns.get_level_values(0):
                    frame = data[ticker]
                elif ticker in data.columns.get_level_values(1):
                    frame = data.xs(ticker, axis=1, level=1)
                else:
                    continue
            else:
                frame = data

            close = frame["Close"].dropna()

            if close.empty:
                continue

            last_ts = pd.Timestamp(close.index[-1])

            if last_ts.tzinfo is None:
                last_ts = last_ts.tz_localize("UTC")
            else:
                last_ts = last_ts.tz_convert("UTC")

            out[ticker] = {
                "price": float(close.iloc[-1]),
                "updated_at": last_ts.isoformat(),
            }

        except Exception:
            pass

    return out


def main():
    with sqlite3.connect(DB_PATH) as conn:
        positions = pd.read_sql_query(
            """
            SELECT *
            FROM positions
            WHERE portfolio_id = 'default'
            """,
            conn,
        )

        portfolio_state = pd.read_sql_query(
            """
            SELECT cash
            FROM portfolio_state
            WHERE portfolio_id = 'default'
            """,
            conn,
        )

    open_positions = positions[
        positions.status == "OPEN"
    ].copy()

    closed_positions = positions[
        positions.status == "CLOSED"
    ].copy()

    tickers = (
        open_positions.ticker.astype(str).tolist()
        if not open_positions.empty
        else []
    )

    price_data = prices(tickers)

    # ---------------------------------------------------------
    # OPEN POSITIONS
    # ---------------------------------------------------------

    opens = []

    for _, row in open_positions.iterrows():
        ticker = str(row.ticker)

        price_info = price_data.get(ticker, {})

        mark = float(
            price_info.get(
                "price",
                float(row.entry_price),
            )
        )

        price_updated_at = price_info.get("updated_at")

        entry = float(row.entry_price)
        shares = int(row.shares)

        risk = entry - float(row.stop)

        pnl = (mark - entry) * shares

        ret = (
            (mark - entry) / entry
            if entry
            else None
        )

        current_r = (
            (mark - entry) / risk
            if risk > 0
            else None
        )

        entry_date = pd.to_datetime(
            row.entry_date,
            utc=True,
            errors="coerce",
        )

        holding_days = None

        if pd.notna(entry_date):
            holding_days = max(
                0,
                (
                    pd.Timestamp.now(tz="UTC")
                    - entry_date
                ).total_seconds()
                / 86400,
            )

        opens.append(
            {
                "id": int(row.id),
                "rank": int(row["rank"]),
                "ticker": ticker,
                "entry_date": str(row.entry_date),
                "entry_price": entry,
                "mark_price": mark,
                "price_updated_at": price_updated_at,
                "shares": shares,
                "notional": float(row.notional),
                "stop": float(row.stop),
                "target": float(row.target),
                "unrealized_pnl": pnl,
                "unrealized_return": ret,
                "current_r": current_r,
                "holding_days": holding_days,
                "strategy_type": (
                    row.get("strategy_type")
                    or "SWING"
                ),
                "planned_horizon_sessions": int(
                    row.get(
                        "planned_horizon_sessions"
                    )
                    or 20
                ),
                "signal": signal(
                    row.get("signal_snapshot")
                ),
            }
        )

    # ---------------------------------------------------------
    # CLOSED POSITIONS
    # ---------------------------------------------------------

    closed = []

    if not closed_positions.empty:
        closed_positions = closed_positions.sort_values(
            "exit_date",
            ascending=False,
        )

    for _, row in closed_positions.iterrows():
        entry = float(row.entry_price)

        exit_price = clean(row.exit_price)
        realized_pnl = clean(row.realized_pnl)

        realized_return = None

        if (
            exit_price is not None
            and entry != 0
        ):
            realized_return = (
                float(exit_price) - entry
            ) / entry

        closed.append(
            {
                "id": int(row.id),
                "rank": clean(row.get("rank")),
                "ticker": str(row.ticker),
                "entry_date": str(row.entry_date),
                "entry_price": entry,
                "exit_date": clean(row.exit_date),
                "exit_price": exit_price,
                "realized_pnl": realized_pnl,
                "realized_return": realized_return,
                "close_reason": clean(row.close_reason),
                "strategy_type": (
                    row.get("strategy_type")
                    or "SWING"
                ),
                "planned_horizon_sessions": (
                    int(row.get("planned_horizon_sessions"))
                    if pd.notna(
                        row.get("planned_horizon_sessions")
                    )
                    else 20
                ),
                "signal": signal(
                    row.get("signal_snapshot")
                ),
            }
        )

    # ---------------------------------------------------------
    # PORTFOLIO SUMMARY
    # ---------------------------------------------------------

    cash = (
        float(portfolio_state.iloc[0].cash)
        if not portfolio_state.empty
        else 0.0
    )

    market_value = sum(
        position["mark_price"]
        * position["shares"]
        for position in opens
    )

    unrealized_pnl = sum(
        position["unrealized_pnl"]
        for position in opens
    )

    realized_pnl = sum(
        position["realized_pnl"] or 0
        for position in closed
    )

    equity = cash + market_value

    latest_prices = [
        position["price_updated_at"]
        for position in opens
        if position["price_updated_at"]
    ]

    data = {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "price_source": "Yahoo Finance",

        "price_interval": "1m",

        "latest_price_at": (
            max(latest_prices)
            if latest_prices
            else None
        ),

        "summary": {
            "cash": cash,
            "market_value": market_value,
            "equity": equity,
            "unrealized_pnl": unrealized_pnl,
            "realized_pnl": realized_pnl,
            "open_positions": len(open_positions),
            "closed_positions": len(closed),
        },

        "open": opens,

        "closed": closed,
    }

    with open(
        OUTPUT,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
            default=clean,
        )

    print(
        f"Dashboard data written: {OUTPUT}; "
        f"Open: {len(open_positions)}; "
        f"Closed: {len(closed)}; "
        f"Equity: {equity:.2f}; "
        f"Latest price: {data['latest_price_at']}"
    )


if __name__ == "__main__":
    main()