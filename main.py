from __future__ import annotations

from pathlib import Path

import yaml

from agents.scanner import run_scan
from agents.technical import analyze_candidates
from database.db import ensure_portfolio_schema, save_dataframe
from portfolio.paper_trading import PaperPortfolio
from scoring.signal_engine import rank_top10


def load_config(path: str = "config/config.yaml") -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def run_pipeline(config: dict | None = None):
    cfg = config or load_config()
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

    latest_prices = {
        ticker: float(frame["Close"].iloc[-1])
        for ticker, frame in history.items()
        if not frame.empty
    }

    portfolio = PaperPortfolio(
        db_path=db_path,
        starting_cash=cfg["portfolio"]["starting_cash"],
        max_positions=cfg["portfolio"]["positions"],
    )

    closed = portfolio.evaluate_exits(latest_prices)
    open_positions = portfolio.sync_from_top10(top10)
    snapshot = portfolio.snapshot(latest_prices)
    portfolio_status = portfolio.status(latest_prices)

    save_dataframe(scan, "scans", db_path)
    save_dataframe(technical, "technical_signals", db_path)
    save_dataframe(top10, "top10", db_path)
    save_dataframe(open_positions, "portfolio_status", db_path)

    return (
        scan,
        top10,
        open_positions,
        snapshot,
        portfolio_status,
        closed,
    )


if __name__ == "__main__":
    scan, top10, open_positions, snapshot, portfolio_status, closed = run_pipeline()

    print(f"Scanned: {len(scan)} symbols")
    print("\nTop 10:")
    print(
        top10[
            ["rank", "ticker", "technical_score", "entry", "stop", "target", "risk_reward"]
        ].to_string(index=False)
    )

    print("\nClosed this run:")
    print(closed if closed else "None")

    print("\nOpen paper positions:")
    if open_positions.empty:
        print("None")
    else:
        print(
            open_positions[
                ["rank", "ticker", "entry_price", "shares", "notional", "stop", "target"]
            ].to_string(index=False)
        )

    print("\nPortfolio snapshot:")
    print(snapshot)
