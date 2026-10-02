
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import yfinance as yf


DB_PATH = Path("data/stock_scout.db")
PORTFOLIO_ID = "default"


def load_data():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database non trovato: {DB_PATH}"
        )

    with sqlite3.connect(DB_PATH) as conn:
        state = pd.read_sql_query(
            """
            SELECT *
            FROM portfolio_state
            WHERE portfolio_id = ?
            """,
            conn,
            params=(PORTFOLIO_ID,),
        )

        positions = pd.read_sql_query(
            """
            SELECT *
            FROM positions
            WHERE portfolio_id = ?
            """,
            conn,
            params=(PORTFOLIO_ID,),
        )

        trades = pd.read_sql_query(
            """
            SELECT *
            FROM trades
            WHERE portfolio_id = ?
            ORDER BY timestamp, id
            """,
            conn,
            params=(PORTFOLIO_ID,),
        )

    if state.empty:
        raise RuntimeError("Portafoglio non inizializzato.")

    return state.iloc[0], positions, trades


def get_market_prices(tickers):
    prices = {}

    for ticker in sorted(set(tickers)):
        try:
            data = yf.download(
                ticker,
                period="5d",
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=False,
            )

            if data.empty or "Close" not in data:
                continue

            close = data["Close"].dropna()

            if not close.empty:
                value = close.iloc[-1]

                if hasattr(value, "item"):
                    value = value.item()

                prices[ticker] = float(value)

        except Exception as exc:
            print(f"Prezzo non disponibile per {ticker}: {exc}")

    return prices


def money(value):
    return f"${value:,.2f}"


def main():
    state, positions, trades = load_data()

    starting_cash = float(state["starting_cash"])
    cash = float(state["cash"])

    open_positions = positions[
        positions["status"] == "OPEN"
    ].copy()

    closed_positions = positions[
        positions["status"] == "CLOSED"
    ].copy()

    tickers = open_positions["ticker"].tolist()
    prices = get_market_prices(tickers)

    if not open_positions.empty:
        open_positions["mark_price"] = (
            open_positions["ticker"]
            .map(prices)
            .fillna(open_positions["entry_price"])
        )

        open_positions["price_source"] = (
            open_positions["ticker"]
            .map(
                lambda ticker:
                "Yahoo Finance"
                if ticker in prices
                else "Prezzo ingresso (fallback)"
            )
        )

        open_positions["market_value"] = (
            open_positions["mark_price"]
            * open_positions["shares"]
        )

        open_positions["unrealized_pnl"] = (
            open_positions["mark_price"]
            - open_positions["entry_price"]
        ) * open_positions["shares"]

    else:
        open_positions["market_value"] = []
        open_positions["unrealized_pnl"] = []
        open_positions["price_source"] = []

    realized_pnl = (
        float(closed_positions["realized_pnl"].sum())
        if not closed_positions.empty
        else 0.0
    )

    unrealized_pnl = (
        float(open_positions["unrealized_pnl"].sum())
        if not open_positions.empty
        else 0.0
    )

    market_value = (
        float(open_positions["market_value"].sum())
        if not open_positions.empty
        else 0.0
    )

    equity = cash + market_value
    total_pnl = equity - starting_cash

    closed_trades = trades[
        trades["side"] == "SELL"
    ].copy()

    if not closed_trades.empty:
        winners = closed_trades[
            closed_trades["realized_pnl"] > 0
        ]

        losers = closed_trades[
            closed_trades["realized_pnl"] < 0
        ]

        win_rate = (
            len(winners) / len(closed_trades) * 100
        )

        avg_win = (
            float(winners["realized_pnl"].mean())
            if not winners.empty
            else 0.0
        )

        avg_loss = (
            float(losers["realized_pnl"].mean())
            if not losers.empty
            else 0.0
        )

    else:
        winners = closed_trades
        losers = closed_trades
        win_rate = 0.0
        avg_win = 0.0
        avg_loss = 0.0

    print()
    print("=" * 58)
    print("       STOCK SCOUT AI — PERFORMANCE REPORT")
    print("=" * 58)

    print(f"Capitale iniziale:       {money(starting_cash)}")
    print(f"Liquidità disponibile:   {money(cash)}")
    print(f"Valore posizioni:        {money(market_value)}")
    print(f"Equity stimata:          {money(equity)}")
    print(f"P&L realizzato:          {money(realized_pnl)}")
    print(f"P&L non realizzato:      {money(unrealized_pnl)}")
    print(f"P&L complessivo:         {money(total_pnl)}")

    if starting_cash:
        print(
            "Rendimento complessivo: "
            f"{total_pnl / starting_cash * 100:.2f}%"
        )

    print("-" * 58)
    print(f"Posizioni aperte:        {len(open_positions)}")
    print(f"Operazioni chiuse:       {len(closed_trades)}")
    print(f"Operazioni positive:     {len(winners)}")
    print(f"Operazioni negative:     {len(losers)}")
    print(f"Win rate:                {win_rate:.2f}%")
    print(f"Profitto medio:          {money(avg_win)}")
    print(f"Perdita media:           {money(avg_loss)}")

    print("-" * 58)
    print("RISULTATI PER MOTIVO DI CHIUSURA")

    if not closed_trades.empty:
        summary = (
            closed_trades
            .groupby("reason")
            .agg(
                operazioni=("id", "count"),
                pnl_totale=("realized_pnl", "sum"),
                pnl_medio=("realized_pnl", "mean"),
            )
        )

        print(summary.to_string())

    else:
        print("Nessuna operazione chiusa.")

    print("-" * 58)
    print("POSIZIONI APERTE")

    if not open_positions.empty:
        columns = [
            "ticker",
            "shares",
            "entry_price",
            "mark_price",
            "unrealized_pnl",
            "price_source",
        ]

        print(
            open_positions[columns].to_string(
                index=False,
                formatters={
                    "entry_price": lambda x: f"{x:.2f}",
                    "mark_price": lambda x: f"{x:.2f}",
                    "unrealized_pnl": lambda x: f"{x:.2f}",
                },
            )
        )

    else:
        print("Nessuna posizione aperta.")

    print("=" * 58)
    print(
        "Nota: report di paper trading; "
        "non vengono inviati ordini reali."
    )


if __name__ == "__main__":
    main()