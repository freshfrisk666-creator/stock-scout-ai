import json
import sqlite3

import pandas as pd

from database.db import ensure_portfolio_schema, get_connection
from portfolio.paper_trading import PaperPortfolio, build_equal_weight_orders
from scoring.signal_engine import rank_top10


def test_rank_and_first_run_preview():
    technical = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "technical_score": 90.0,
                "risk_reward": 2.0,
                "entry": 100.0,
                "stop": 90.0,
                "target": 120.0,
            },
            {
                "ticker": "BBB",
                "technical_score": 80.0,
                "risk_reward": 2.0,
                "entry": 50.0,
                "stop": 45.0,
                "target": 60.0,
            },
        ]
    )

    top = rank_top10(technical, 2)

    assert top["ticker"].tolist() == ["AAA", "BBB"]
    assert top["rank"].tolist() == [1, 2]

    orders = build_equal_weight_orders(top, 10_000, 2)

    assert orders["shares"].tolist() == [50, 100]
    assert round(float(orders["notional"].sum()), 6) == 10_000


def test_persistent_portfolio_signal_attribution_and_close(tmp_path):
    db_path = tmp_path / "paper.db"

    top10 = pd.DataFrame(
        [
            {
                "rank": 1,
                "ticker": "AAA",
                "technical_score": 90.0,
                "trend_score": 91.0,
                "momentum_score": 88.0,
                "rsi_score": 82.0,
                "volume_score": 77.0,
                "breakout_score": 80.0,
                "momentum_21d": 0.12,
                "momentum_63d": 0.31,
                "volume_ratio_20d": 1.4,
                "breakout_strength_20d": 0.06,
                "risk_reward": 2.0,
                "methodology": "M2 deterministic technical",
                "entry": 100.0,
                "stop": 90.0,
                "target": 120.0,
            },
            {
                "rank": 2,
                "ticker": "BBB",
                "technical_score": 80.0,
                "trend_score": 75.0,
                "momentum_score": 79.0,
                "entry": 50.0,
                "stop": 45.0,
                "target": 60.0,
            },
        ]
    )

    portfolio = PaperPortfolio(
        db_path=str(db_path),
        starting_cash=10_000,
        max_positions=2,
    )

    opened = portfolio.sync_from_top10(
        top10,
        as_of="2026-09-22T10:00:00+00:00",
    )
    assert len(opened) == 2
    assert set(opened["ticker"]) == {"AAA", "BBB"}

    snapshot_text = opened.loc[opened["ticker"] == "AAA", "signal_snapshot"].iloc[0]
    snapshot = json.loads(snapshot_text)
    assert snapshot["ticker"] == "AAA"
    assert snapshot["technical_score"] == 90.0
    assert snapshot["trend_score"] == 91.0
    assert snapshot["momentum_score"] == 88.0
    assert snapshot["_snapshot_version"] == "v1"

    with get_connection(str(db_path)) as conn:
        buy = conn.execute(
            """
            SELECT signal_snapshot
            FROM trades
            WHERE ticker = ? AND side = 'BUY'
            """,
            ("AAA",),
        ).fetchone()
        assert buy[0] == snapshot_text

    portfolio_snapshot = portfolio.snapshot(
        {"AAA": 110.0, "BBB": 55.0},
        as_of="2026-09-22T11:00:00+00:00",
    )
    assert round(portfolio_snapshot["equity"], 6) == 11_000.0
    assert round(portfolio_snapshot["unrealized_pnl"], 6) == 1000.0

    closed = portfolio.evaluate_exits(
        {"AAA": 120.0, "BBB": 55.0},
        as_of="2026-09-22T15:00:00+00:00",
    )

    assert len(closed) == 1
    assert closed[0]["ticker"] == "AAA"
    assert closed[0]["reason"] == "TARGET_CLOSE"
    assert round(closed[0]["realized_pnl"], 6) == 1000.0
    assert closed[0]["signal_snapshot"] == snapshot_text

    open_positions = portfolio.open_positions()
    assert open_positions["ticker"].tolist() == ["BBB"]

    with get_connection(str(db_path)) as conn:
        trade_count = conn.execute(
            "SELECT COUNT(*) FROM trades"
        ).fetchone()[0]
        snapshot_count = conn.execute(
            "SELECT COUNT(*) FROM portfolio_snapshots"
        ).fetchone()[0]
        buy_snapshot, sell_snapshot = conn.execute(
            """
            SELECT
                (SELECT signal_snapshot FROM trades WHERE ticker = 'AAA' AND side = 'BUY' ORDER BY id LIMIT 1),
                (SELECT signal_snapshot FROM trades WHERE ticker = 'AAA' AND side = 'SELL' ORDER BY id LIMIT 1)
            """
        ).fetchone()

    assert trade_count == 3
    assert snapshot_count == 1
    assert buy_snapshot == sell_snapshot == snapshot_text


def test_signal_attribution_schema_migrates_existing_database(tmp_path):
    db_path = tmp_path / "legacy.db"

    # Simulate the pre-Signal-Attribution schema.
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE portfolio_state (
                portfolio_id TEXT PRIMARY KEY,
                starting_cash REAL NOT NULL,
                cash REAL NOT NULL,
                max_positions INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                rank INTEGER NOT NULL,
                entry_date TEXT NOT NULL,
                entry_price REAL NOT NULL,
                shares INTEGER NOT NULL,
                notional REAL NOT NULL,
                stop REAL NOT NULL,
                target REAL NOT NULL,
                status TEXT NOT NULL,
                technical_score REAL,
                exit_date TEXT,
                exit_price REAL,
                realized_pnl REAL DEFAULT 0,
                close_reason TEXT
            );

            CREATE TABLE trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_id TEXT NOT NULL,
                position_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                side TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                price REAL NOT NULL,
                shares INTEGER NOT NULL,
                notional REAL NOT NULL,
                cash_after REAL NOT NULL,
                reason TEXT NOT NULL,
                realized_pnl REAL DEFAULT 0
            );
            """
        )
        conn.execute(
            """
            INSERT INTO portfolio_state(
                portfolio_id, starting_cash, cash, max_positions, updated_at
            ) VALUES ('default', 10000, 10000, 2, '2026-09-22T10:00:00+00:00')
            """
        )
        conn.execute(
            """
            INSERT INTO positions(
                portfolio_id, ticker, rank, entry_date, entry_price,
                shares, notional, stop, target, status, technical_score,
                exit_date, exit_price, realized_pnl, close_reason
            ) VALUES ('default', 'LEGACY', 1, '2026-09-22T10:00:00+00:00',
                      100, 10, 1000, 90, 120, 'OPEN', 70,
                      NULL, NULL, 0, NULL)
            """
        )

    ensure_portfolio_schema(str(db_path))

    with get_connection(str(db_path)) as conn:
        position_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(positions)").fetchall()
        }
        trade_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(trades)").fetchall()
        }
        legacy_row = conn.execute(
            "SELECT ticker, technical_score FROM positions WHERE ticker = 'LEGACY'"
        ).fetchone()

    assert "signal_snapshot" in position_columns
    assert "signal_snapshot" in trade_columns
    assert tuple(legacy_row) == ("LEGACY", 70.0)
