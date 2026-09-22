from __future__ import annotations

from datetime import datetime, timezone
import math
import sqlite3

import pandas as pd

from database.db import ensure_portfolio_schema, get_connection


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_equal_weight_orders(
    top10: pd.DataFrame,
    starting_cash: float = 100_000,
    positions: int = 10,
) -> pd.DataFrame:
    """Backward-compatible first-run order preview."""
    if top10.empty:
        return pd.DataFrame(
            columns=[
                "rank", "ticker", "entry", "shares", "notional",
                "stop", "target", "cash_remaining",
            ]
        )

    capital_per_position = float(starting_cash) / max(1, int(positions))
    cash = float(starting_cash)
    rows = []

    for _, row in top10.head(positions).iterrows():
        entry = float(row["entry"])
        shares = math.floor(capital_per_position / entry)
        notional = shares * entry
        cash -= notional
        rows.append(
            {
                "rank": int(row["rank"]),
                "ticker": row["ticker"],
                "entry": entry,
                "shares": shares,
                "notional": notional,
                "stop": float(row["stop"]),
                "target": float(row["target"]),
                "cash_remaining": cash,
            }
        )

    return pd.DataFrame(rows)


class PaperPortfolio:
    """Persistent SQLite-backed V1 paper portfolio."""

    def __init__(
        self,
        db_path: str = "data/stock_scout.db",
        starting_cash: float = 100_000,
        max_positions: int = 10,
        portfolio_id: str = "default",
    ) -> None:
        self.db_path = db_path
        self.portfolio_id = portfolio_id
        self.starting_cash = float(starting_cash)
        self.max_positions = int(max_positions)
        ensure_portfolio_schema(db_path)

        with get_connection(db_path) as conn:
            row = conn.execute(
                """
                SELECT starting_cash, cash, max_positions
                FROM portfolio_state
                WHERE portfolio_id = ?
                """,
                (portfolio_id,),
            ).fetchone()

            if row is None:
                conn.execute(
                    """
                    INSERT INTO portfolio_state(
                        portfolio_id, starting_cash, cash, max_positions, updated_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        portfolio_id,
                        self.starting_cash,
                        self.starting_cash,
                        self.max_positions,
                        _utc_now(),
                    ),
                )
            else:
                self.starting_cash = float(row[0])
                self.max_positions = int(row[2])

    def _get_cash(self, conn: sqlite3.Connection) -> float:
        row = conn.execute(
            "SELECT cash FROM portfolio_state WHERE portfolio_id = ?",
            (self.portfolio_id,),
        ).fetchone()
        return float(row[0])

    def _set_cash(self, conn: sqlite3.Connection, cash: float) -> None:
        conn.execute(
            """
            UPDATE portfolio_state
            SET cash = ?, updated_at = ?
            WHERE portfolio_id = ?
            """,
            (float(cash), _utc_now(), self.portfolio_id),
        )

    def open_positions(self) -> pd.DataFrame:
        with get_connection(self.db_path) as conn:
            return pd.read_sql_query(
                """
                SELECT *
                FROM positions
                WHERE portfolio_id = ? AND status = 'OPEN'
                ORDER BY rank ASC, ticker ASC
                """,
                conn,
                params=(self.portfolio_id,),
            )

    def all_trades(self) -> pd.DataFrame:
        with get_connection(self.db_path) as conn:
            return pd.read_sql_query(
                """
                SELECT *
                FROM trades
                WHERE portfolio_id = ?
                ORDER BY id ASC
                """,
                conn,
                params=(self.portfolio_id,),
            )

    def sync_from_top10(
        self,
        top10: pd.DataFrame,
        as_of: str | None = None,
    ) -> pd.DataFrame:
        """Fill free portfolio slots from the current Top 10."""
        as_of = as_of or _utc_now()

        if top10.empty:
            return self.open_positions()

        with get_connection(self.db_path) as conn:
            existing = conn.execute(
                """
                SELECT ticker
                FROM positions
                WHERE portfolio_id = ? AND status = 'OPEN'
                """,
                (self.portfolio_id,),
            ).fetchall()

            open_tickers = {r[0] for r in existing}
            available_slots = max(0, self.max_positions - len(open_tickers))
            target_notional = self.starting_cash / max(1, self.max_positions)
            cash = self._get_cash(conn)

            for _, row in top10.head(self.max_positions).iterrows():
                if available_slots <= 0:
                    break

                ticker = str(row["ticker"])
                if ticker in open_tickers:
                    continue

                entry = float(row["entry"])
                shares = math.floor(target_notional / entry)
                if shares <= 0:
                    continue

                notional = shares * entry
                if notional > cash:
                    continue

                cursor = conn.execute(
                    """
                    INSERT INTO positions(
                        portfolio_id, ticker, rank, entry_date, entry_price,
                        shares, notional, stop, target, status,
                        technical_score, exit_date, exit_price,
                        realized_pnl, close_reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, NULL, NULL, 0, NULL)
                    """,
                    (
                        self.portfolio_id,
                        ticker,
                        int(row["rank"]),
                        as_of,
                        entry,
                        shares,
                        notional,
                        float(row["stop"]),
                        float(row["target"]),
                        float(row.get("technical_score", 0.0)),
                    ),
                )
                position_id = cursor.lastrowid

                cash -= notional
                available_slots -= 1
                open_tickers.add(ticker)

                conn.execute(
                    """
                    INSERT INTO trades(
                        portfolio_id, position_id, ticker, side, timestamp,
                        price, shares, notional, cash_after, reason, realized_pnl
                    ) VALUES (?, ?, ?, 'BUY', ?, ?, ?, ?, ?, 'OPEN_POSITION', 0)
                    """,
                    (
                        self.portfolio_id,
                        position_id,
                        ticker,
                        as_of,
                        entry,
                        shares,
                        notional,
                        cash,
                    ),
                )

            self._set_cash(conn, cash)

        return self.open_positions()

    def evaluate_exits(
        self,
        latest_prices: dict[str, float],
        as_of: str | None = None,
    ) -> list[dict]:
        """Close OPEN positions when latest price crosses stop or target."""
        as_of = as_of or _utc_now()
        closed = []

        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT id, ticker, shares, entry_price, stop, target
                FROM positions
                WHERE portfolio_id = ? AND status = 'OPEN'
                """,
                (self.portfolio_id,),
            ).fetchall()

            cash = self._get_cash(conn)

            for position_id, ticker, shares, entry_price, stop, target in rows:
                if ticker not in latest_prices:
                    continue

                price = float(latest_prices[ticker])
                reason = None

                if price <= float(stop):
                    reason = "STOP_CLOSE"
                elif price >= float(target):
                    reason = "TARGET_CLOSE"

                if reason is None:
                    continue

                realized_pnl = (price - float(entry_price)) * int(shares)
                notional = price * int(shares)
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
                    (
                        as_of,
                        price,
                        realized_pnl,
                        reason,
                        position_id,
                    ),
                )

                conn.execute(
                    """
                    INSERT INTO trades(
                        portfolio_id, position_id, ticker, side, timestamp,
                        price, shares, notional, cash_after, reason, realized_pnl
                    ) VALUES (?, ?, ?, 'SELL', ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.portfolio_id,
                        position_id,
                        ticker,
                        as_of,
                        price,
                        int(shares),
                        notional,
                        cash,
                        reason,
                        realized_pnl,
                    ),
                )

                closed.append(
                    {
                        "position_id": position_id,
                        "ticker": ticker,
                        "exit_price": price,
                        "shares": int(shares),
                        "realized_pnl": realized_pnl,
                        "reason": reason,
                    }
                )

            self._set_cash(conn, cash)

        return closed

    def snapshot(
        self,
        latest_prices: dict[str, float] | None = None,
        as_of: str | None = None,
    ) -> dict:
        latest_prices = latest_prices or {}
        as_of = as_of or _utc_now()

        with get_connection(self.db_path) as conn:
            cash = self._get_cash(conn)
            rows = conn.execute(
                """
                SELECT ticker, shares, entry_price
                FROM positions
                WHERE portfolio_id = ? AND status = 'OPEN'
                """,
                (self.portfolio_id,),
            ).fetchall()

            market_value = 0.0
            unrealized_pnl = 0.0

            for ticker, shares, entry_price in rows:
                mark = float(latest_prices.get(ticker, entry_price))
                market_value += mark * int(shares)
                unrealized_pnl += (mark - float(entry_price)) * int(shares)

            equity = cash + market_value

            conn.execute(
                """
                INSERT INTO portfolio_snapshots(
                    portfolio_id, timestamp, cash,
                    market_value, equity, unrealized_pnl
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    self.portfolio_id,
                    as_of,
                    cash,
                    market_value,
                    equity,
                    unrealized_pnl,
                ),
            )

        return {
            "portfolio_id": self.portfolio_id,
            "timestamp": as_of,
            "cash": cash,
            "market_value": market_value,
            "equity": equity,
            "unrealized_pnl": unrealized_pnl,
            "open_positions": len(rows),
        }

    def status(self, latest_prices: dict[str, float] | None = None) -> pd.DataFrame:
        latest_prices = latest_prices or {}
        positions = self.open_positions()

        if positions.empty:
            return positions

        positions = positions.copy()
        positions["mark_price"] = positions["ticker"].map(latest_prices)
        positions["mark_price"] = positions["mark_price"].fillna(positions["entry_price"])
        positions["market_value"] = positions["mark_price"] * positions["shares"]
        positions["unrealized_pnl"] = (
            positions["mark_price"] - positions["entry_price"]
        ) * positions["shares"]

        with get_connection(self.db_path) as conn:
            positions["cash"] = self._get_cash(conn)

        return positions
