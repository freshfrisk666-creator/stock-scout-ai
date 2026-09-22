from __future__ import annotations

from pathlib import Path

import yaml

from agents.scanner import run_scan
from agents.technical import analyze_candidates
from database.db import save_dataframe
from portfolio.paper_trading import build_equal_weight_orders
from scoring.signal_engine import rank_top10


def load_config(path: str = "config/config.yaml") -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def run_pipeline(config: dict | None = None):
    cfg = config or load_config()
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
    paper = build_equal_weight_orders(
        top10,
        starting_cash=cfg["portfolio"]["starting_cash"],
        positions=cfg["portfolio"]["positions"],
    )
    save_dataframe(scan, "scans", cfg["database"]["path"])
    save_dataframe(technical, "technical_signals", cfg["database"]["path"])
    save_dataframe(top10, "top10", cfg["database"]["path"])
    save_dataframe(paper, "paper_orders", cfg["database"]["path"])
    return scan, top10, paper


if __name__ == "__main__":
    scan, top10, paper = run_pipeline()
    print(f"Scanned: {len(scan)} symbols")
    print(top10[["rank", "ticker", "technical_score", "entry", "stop", "target", "risk_reward"]].to_string(index=False))
    print("\nPaper orders:")
    print(paper.to_string(index=False))
