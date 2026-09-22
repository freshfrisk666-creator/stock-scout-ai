import pandas as pd

from database.db import get_connection
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


def test_persistent_portfolio_open_and_close(tmp_path):
    db_path = tmp_path / "paper.db"

    top10 = pd.DataFrame(
        [
            {
                "rank": 1,
                "ticker": "AAA",
                "technical_score": 90.0,
                "entry": 100.0,
                "stop": 90.0,
                "target": 120.0,
            },
            {
                "rank": 2,
                "ticker": "BBB",
                "technical_score": 80.0,
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

    snapshot = portfolio.snapshot(
        {"AAA": 110.0, "BBB": 55.0},
        as_of="2026-09-22T11:00:00+00:00",
    )
    assert round(snapshot["equity"], 6) == 11_000.0
    assert round(snapshot["unrealized_pnl"], 6) == 1000.0

    closed = portfolio.evaluate_exits(
        {"AAA": 120.0, "BBB": 55.0},
        as_of="2026-09-22T15:00:00+00:00",
    )

    assert len(closed) == 1
    assert closed[0]["ticker"] == "AAA"
    assert closed[0]["reason"] == "TARGET_CLOSE"
    assert round(closed[0]["realized_pnl"], 6) == 1000.0

    open_positions = portfolio.open_positions()
    assert open_positions["ticker"].tolist() == ["BBB"]

    with get_connection(str(db_path)) as conn:
        trade_count = conn.execute(
            "SELECT COUNT(*) FROM trades"
        ).fetchone()[0]
        snapshot_count = conn.execute(
            "SELECT COUNT(*) FROM portfolio_snapshots"
        ).fetchone()[0]

    assert trade_count == 3
    assert snapshot_count == 1
