import pandas as pd
from portfolio.paper_trading import build_equal_weight_orders
from scoring.signal_engine import rank_top10


def test_rank_and_paper_orders():
    technical = pd.DataFrame([
        {"ticker": "AAA", "technical_score": 90.0, "risk_reward": 2.0, "entry": 100.0, "stop": 90.0, "target": 120.0},
        {"ticker": "BBB", "technical_score": 80.0, "risk_reward": 2.0, "entry": 50.0, "stop": 45.0, "target": 60.0},
    ])
    top = rank_top10(technical, 2)
    assert top["ticker"].tolist() == ["AAA", "BBB"]
    assert top["rank"].tolist() == [1, 2]
    orders = build_equal_weight_orders(top, 10_000, 2)
    assert orders["shares"].tolist() == [50, 100]
    assert round(float(orders["notional"].sum()), 6) == 10_000
