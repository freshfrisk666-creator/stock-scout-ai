import json
import sqlite3

import pandas as pd

from analysis.trade_analysis import analyze_closed_trade, analyze_closed_trades, load_closed_trade_analysis


def _snapshot():
    return json.dumps({
        "_snapshot_version": "v1",
        "ticker": "AAA",
        "rank": 1,
        "technical_score": 86.2,
        "trend_score": 100.0,
        "momentum_score": 88.8,
        "rsi_score": 100.0,
        "volume_score": 53.4,
        "breakout_score": 73.3,
        "entry": 100.0,
        "stop": 90.0,
        "target": 120.0,
    })


def test_analyze_closed_trade_target_win():
    result = analyze_closed_trade({
        "position_id": 1,
        "ticker": "AAA",
        "rank": 1,
        "entry_date": "2026-09-22T10:00:00+00:00",
        "entry_price": 100.0,
        "shares": 10,
        "stop": 90.0,
        "target": 120.0,
        "exit_date": "2026-09-25T10:00:00+00:00",
        "exit_price": 120.0,
        "realized_pnl": 200.0,
        "close_reason": "TARGET_CLOSE",
        "signal_snapshot": _snapshot(),
    })

    assert result["outcome"] == "WIN"
    assert result["close_reason"] == "TARGET_CLOSE"
    assert result["return_pct"] == 20.0
    assert result["realized_r_multiple"] == 2.0
    assert result["holding_days"] == 3.0
    assert "trend" in result["signal_strengths"]
    assert result["snapshot_version"] == "v1"
    assert "target reached" in result["explanation"]


def test_analyze_closed_trade_stop_loss():
    result = analyze_closed_trade({
        "position_id": 2,
        "ticker": "BBB",
        "entry_price": 100.0,
        "shares": 10,
        "stop": 90.0,
        "target": 120.0,
        "exit_price": 90.0,
        "realized_pnl": -100.0,
        "close_reason": "STOP_CLOSE",
        "signal_snapshot": _snapshot(),
    })

    assert result["outcome"] == "LOSS"
    assert result["realized_r_multiple"] == -1.0
    assert "stop reached" in result["explanation"]


def test_analyze_closed_trades_empty():
    result = analyze_closed_trades(pd.DataFrame())
    assert result.empty
    assert "outcome" in result.columns


def test_load_closed_trade_analysis_from_sqlite(tmp_path):
    db_path = tmp_path / "analysis.db"

    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE positions (
                id INTEGER PRIMARY KEY,
                portfolio_id TEXT,
                ticker TEXT,
                rank INTEGER,
                entry_date TEXT,
                entry_price REAL,
                shares INTEGER,
                notional REAL,
                stop REAL,
                target REAL,
                status TEXT,
                technical_score REAL,
                signal_snapshot TEXT,
                exit_date TEXT,
                exit_price REAL,
                realized_pnl REAL,
                close_reason TEXT
            );
            """
        )
        conn.execute(
            """
            INSERT INTO positions(
                id, portfolio_id, ticker, rank, entry_date, entry_price,
                shares, notional, stop, target, status, technical_score,
                signal_snapshot, exit_date, exit_price, realized_pnl, close_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                7, "default", "AAA", 1, "2026-09-22T10:00:00+00:00", 100.0,
                10, 1000.0, 90.0, 120.0, "CLOSED", 86.2, _snapshot(),
                "2026-09-25T10:00:00+00:00", 120.0, 200.0, "TARGET_CLOSE",
            ),
        )

    result = load_closed_trade_analysis(str(db_path))

    assert len(result) == 1
    assert result.loc[0, "ticker"] == "AAA"
    assert result.loc[0, "outcome"] == "WIN"
    assert result.loc[0, "technical_score"] == 86.2
