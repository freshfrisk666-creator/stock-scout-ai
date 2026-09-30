from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import pandas as pd

from database.db import ensure_portfolio_schema, get_connection
from runner.intraday_monitor import (
    evaluate_intraday_exits,
    extract_latest_bars,
    is_market_session,
)


def test_market_session_uses_new_york_time():
    open_dt = datetime(2026, 9, 30, 13, 30, tzinfo=timezone.utc)
    closed_dt = datetime(2026, 9, 30, 20, 1, tzinfo=timezone.utc)

    assert is_market_session(open_dt) is True
    assert is_market_session(closed_dt) is False


def test_extract_latest_bars_from_multiindex():
    index = pd.DatetimeIndex(
        [
            "2026-09-30 13:35:00+00:00",
            "2026-09-30 13:40:00+00:00",
        ]
    )
    columns = pd.MultiIndex.from_product(
        [["AAA", "BBB"], ["Open", "High", "Low", "Close", "Volume"]]
    )
    data = pd.DataFrame(
        [
            [100, 101, 99, 100.5, 1000, 200, 202, 198, 201, 900],
            [100.5, 103, 100, 102, 1100, 201, 203, 200, 202, 1000],
        ],
        index=index,
        columns=columns,
    )

    bars = extract_latest_bars(data, ["AAA", "BBB"])

    assert bars["AAA"]["high"] == 103.0
    assert bars["AAA"]["low"] == 100.0
    assert bars["BBB"]["close"] == 202.0


def _seed_position(tmp_path):
    db_path = tmp_path / "intraday.db"
    from database.db import ensure_portfolio_schema, get_connection

    ensure_portfolio_schema(str(db_path))
    signal_snapshot = json.dumps({
        "_snapshot_version": "v1",
        "ticker": "AAA",
        "technical_score": 90.0,
        "trend_score": 95.0,
        "momentum_score": 85.0,
        "entry": 100.0,
        "stop": 95.0,
        "target": 110.0,
    }, sort_keys=True, separators=(",", ":"))

    with get_connection(str(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO portfolio_state(
                portfolio_id, starting_cash, cash, max_positions, updated_at
            ) VALUES ('default', 1000, 0, 1, '2026-09-30T13:30:00+00:00')
            """,
        )
        conn.execute(
            """
            INSERT INTO positions(
                portfolio_id, ticker, rank, entry_date, entry_price, shares,
                notional, stop, target, status, technical_score, signal_snapshot,
                realized_pnl
            ) VALUES ('default', 'AAA', 1, '2026-09-30T13:30:00+00:00',
                      100, 10, 1000, 95, 110, 'OPEN', 90, ?, 0)
            """,
            (signal_snapshot,),
        )
        conn.commit()
    return db_path


def test_intraday_target_close_preserves_snapshot(tmp_path):
    db_path = _seed_position(tmp_path)

    with get_connection(str(db_path)) as conn:
        snapshot = conn.execute(
            "SELECT signal_snapshot FROM positions WHERE ticker='AAA'"
        ).fetchone()[0]

    bars = {
        "AAA": {
            "timestamp": "2026-09-30T14:45:00+00:00",
            "open": 108.0,
            "high": 111.0,
            "low": 107.0,
            "close": 109.5,
        }
    }

    closed = evaluate_intraday_exits(
        str(db_path),
        bars,
        as_of="2026-09-30T14:45:00+00:00",
        max_bar_age_minutes=20,
    )

    assert len(closed) == 1
    assert closed[0]["reason"] == "TARGET_CLOSE"
    assert closed[0]["exit_price"] == 110.0

    with get_connection(str(db_path)) as conn:
        sell = conn.execute(
            """
            SELECT side, signal_snapshot, price, realized_pnl
            FROM trades
            WHERE ticker='AAA' AND side='SELL'
            ORDER BY id DESC LIMIT 1
            """
        ).fetchone()
        status = conn.execute(
            "SELECT status FROM positions WHERE ticker='AAA'"
        ).fetchone()[0]

    assert sell[0] == "SELL"
    assert sell[1] == snapshot
    assert sell[2] == 110.0
    assert sell[3] == 100.0
    assert status == "CLOSED"


def test_same_bar_stop_and_target_uses_stop(tmp_path):
    db_path = _seed_position(tmp_path)
    bars = {
        "AAA": {
            "timestamp": "2026-09-30T14:45:00+00:00",
            "open": 100.0,
            "high": 111.0,
            "low": 94.0,
            "close": 103.0,
        }
    }

    closed = evaluate_intraday_exits(
        str(db_path),
        bars,
        as_of="2026-09-30T14:45:00+00:00",
        max_bar_age_minutes=20,
    )

    assert len(closed) == 1
    assert closed[0]["reason"] == "STOP_CLOSE"
    assert closed[0]["exit_price"] == 95.0
    assert closed[0]["realized_pnl"] == -50.0


def test_stale_bar_is_ignored(tmp_path):
    db_path = _seed_position(tmp_path)
    bars = {
        "AAA": {
            "timestamp": "2026-09-30T13:00:00+00:00",
            "open": 100.0,
            "high": 111.0,
            "low": 94.0,
            "close": 103.0,
        }
    }

    closed = evaluate_intraday_exits(
        str(db_path),
        bars,
        as_of="2026-09-30T14:45:00+00:00",
        max_bar_age_minutes=20,
    )

    assert closed == []
