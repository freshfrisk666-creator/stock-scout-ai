from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


def get_connection(db_path: str = "data/stock_scout.db") -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path)


def save_dataframe(
    frame: pd.DataFrame,
    table_name: str,
    db_path: str = "data/stock_scout.db",
) -> None:
    if frame is None or frame.empty:
        return
    with get_connection(db_path) as conn:
        frame.to_sql(table_name, conn, if_exists="append", index=False)


def ensure_portfolio_schema(db_path: str = "data/stock_scout.db") -> None:
    with get_connection(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS portfolio_state (
                portfolio_id TEXT PRIMARY KEY,
                starting_cash REAL NOT NULL,
                cash REAL NOT NULL,
                max_positions INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS positions (
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

            CREATE INDEX IF NOT EXISTS idx_positions_portfolio_status
                ON positions(portfolio_id, status);

            CREATE UNIQUE INDEX IF NOT EXISTS uq_open_position_ticker
                ON positions(portfolio_id, ticker, status)
                WHERE status = 'OPEN';

            CREATE TABLE IF NOT EXISTS trades (
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

            CREATE INDEX IF NOT EXISTS idx_trades_portfolio_timestamp
                ON trades(portfolio_id, timestamp);

            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                cash REAL NOT NULL,
                market_value REAL NOT NULL,
                equity REAL NOT NULL,
                unrealized_pnl REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_snapshots_portfolio_timestamp
                ON portfolio_snapshots(portfolio_id, timestamp);
            """
        )
