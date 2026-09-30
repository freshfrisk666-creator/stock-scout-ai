from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any


def run_once(config_path: str = "config/config.yaml") -> dict[str, Any]:
    """Run one complete Stock Scout AI paper-trading cycle.

    The imports are intentionally performed inside the function so the runner
    remains easy to unit-test without starting the market-data stack at import time.
    """
    from main import load_config, run_pipeline

    cfg = load_config(config_path)
    scan, top10, open_positions, snapshot, portfolio_status, closed = run_pipeline(cfg)

    return {
        "config_path": str(Path(config_path)),
        "scanned": len(scan),
        "top10": len(top10),
        "open_positions": len(open_positions),
        "closed_this_run": len(closed),
        "snapshot": snapshot,
        "portfolio_status": portfolio_status,
        "closed": closed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one Stock Scout AI paper-trading cycle")
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="Path to the YAML configuration file",
    )
    args = parser.parse_args()

    result = run_once(args.config)

    print("STOCK SCOUT AI — AUTOMATED PAPER TRADING")
    print(f"Scanned: {result['scanned']}")
    print(f"Top 10: {result['top10']}")
    print(f"Open positions: {result['open_positions']}")
    print(f"Closed this run: {result['closed_this_run']}")
    print(f"Portfolio snapshot: {result['snapshot']}")

    if result["closed"]:
        print("Closed trades:")
        for trade in result["closed"]:
            print(trade)
    else:
        print("Closed trades: None")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
