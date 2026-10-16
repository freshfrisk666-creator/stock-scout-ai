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


def build_selection(cfg: dict):
    """Run the S&P 500 scan and build the current ranked candidate list."""
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
    return scan, history, technical, top10


def persist_selection(
    scan,
    technical,
    top10,
    db_path: str,
    portfolio_status,
):
    save_dataframe(scan, "scans", db_path)
    save_dataframe(technical, "technical_signals", db_path)
    save_dataframe(top10, "top10", db_path)

    # portfolio_status contains only the current state.
    # Replace it each run so rows are not duplicated.
    save_dataframe(
        portfolio_status,
        "portfolio_status",
        db_path,
        if_exists="replace",
    )


def run_eod_pipeline(config: dict | None = None):
    """Run the end-of-day selection/exit cycle.

    IMPORTANT: this cycle never opens new positions.
    """
    cfg = config or load_config()
    db_path = cfg["database"]["path"]

    ensure_portfolio_schema(db_path)

    scan, history, technical, top10 = build_selection(cfg)

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

    # Existing positions may close at EOD if the final available price is
    # already beyond their stop/target.
    closed = portfolio.evaluate_exits(latest_prices)

    # IMPORTANT: do not call sync_from_top10() here.
    # New entries are handled by runner/morning_entry_runner.py.
    open_positions = portfolio.open_positions()

    snapshot = portfolio.snapshot(latest_prices)
    portfolio_status = portfolio.status(latest_prices)

    persist_selection(
        scan=scan,
        technical=technical,
        top10=top10,
        db_path=db_path,
        portfolio_status=portfolio_status,
    )

    return (
        scan,
        top10,
        open_positions,
        snapshot,
        portfolio_status,
        closed,
    )


# Backward-compatible alias used by runner.daily_runner.
def run_pipeline(config: dict | None = None):
    return run_eod_pipeline(config)


if __name__ == "__main__":
    (
        scan,
        top10,
        open_positions,
        snapshot,
        portfolio_status,
        closed,
    ) = run_eod_pipeline()

    print(f"Scanned: {len(scan)} symbols")
    print(f"Top 10 candidates: {len(top10)}")
    print(f"Closed this run: {len(closed)}")
    print(f"Open positions: {len(open_positions)}")
    print(f"Portfolio snapshot: {snapshot}")
