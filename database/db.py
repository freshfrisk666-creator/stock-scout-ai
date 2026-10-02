from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


def get_connection(db_path: str = "data/stock_scout.db") -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _sqlite_type(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "INTEGER"
    if pd.api.types.is_integer_dtype(series):
        return "INTEGER"
    if pd.api.types.is_numeric_dtype(series):
        return "REAL"
    return "TEXT"


def _quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def save_dataframe(
    frame: pd.DataFrame,
    table_name: str,
    db_path: str = "data/stock_scout.db",
    if_exists: str = "append",
) -> None:
    if frame is None or frame.empty:
        return

    if if_exists not in {"append", "replace", "fail"}:
        raise ValueError(
            "if_exists must be one of: 'append', 'replace', 'fail'"
        )

    with get_connection(db_path) as conn:
        existing_tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

        # Schema evolution is needed only when appending to an existing table.
        if if_exists == "append" and table_name in existing_tables:
            existing_columns = {
                row[1]
                for row in conn.execute(
                    f"PRAGMA table_info({_quote_identifier(table_name)})"
                ).fetchall()
            }

            for column in frame.columns:
                if column not in existing_columns:
                    column_type = _sqlite_type(frame[column])
                    conn.execute(
                        f"ALTER TABLE {_quote_identifier(table_name)} "
                        f"ADD COLUMN {_quote_identifier(str(column))} "
                        f"{column_type}"
                    )

        frame.to_sql(
            table_name,
            conn,
            if_exists=if_exists,
            index=False,
        )


def _ensure_columns(conn: sqlite3.Connection) -> None:
    migrations = {
        "positions": {
            "signal_snapshot": "TEXT",
            "strategy_type": "TEXT NOT NULL DEFAULT 'SWING'",
            "planned_horizon_sessions": "INTEGER NOT NULL DEFAULT 20",
        },
        "trades": {
            "signal_snapshot": "TEXT",
            "strategy_type": "TEXT NOT NULL DEFAULT 'SWING'",
        },
    }

    for table, columns in migrations.items():
        existing = {
            row[1]
            for row in conn.execute(
                f"PRAGMA table_info({_quote_identifier(table)})"
            ).fetchall()
        }

        for column, column_type in columns.items():
            if column not in existing:
                conn.execute(
                    f"ALTER TABLE {_quote_identifier(table)} "
                    f"ADD COLUMN {_quote_identifier(column)} {column_type}"
                )


def ensure_portfolio_schema(
    db_path: str = "data/stock_scout.db",
) -> None:
    with get_connection(db_path) as conn:
        conn.executescript(
            '''
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
                signal_snapshot TEXT,
                strategy_type TEXT NOT NULL DEFAULT 'SWING',
                planned_horizon_sessions INTEGER NOT NULL DEFAULT 20,
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
                realized_pnl REAL DEFAULT 0,
                signal_snapshot TEXT,
                strategy_type TEXT NOT NULL DEFAULT 'SWING'
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
            '''
        )

        _ensure_columns(conn)
        conn.commit()
