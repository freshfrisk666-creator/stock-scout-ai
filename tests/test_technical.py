import numpy as np
import pandas as pd
from agents.technical import analyze_ticker, atr_wilder, rsi_wilder, sma


def make_frame(n=260):
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    close = pd.Series(np.linspace(100, 180, n), index=idx)
    return pd.DataFrame({
        "Open": close - 0.5,
        "High": close + 2,
        "Low": close - 2,
        "Close": close,
        "Adj Close": close,
        "Volume": 1_000_000,
    }, index=idx)


def test_indicators_produce_values():
    frame = make_frame()
    assert sma(frame["Close"], 20).iloc[-1] > 0
    assert rsi_wilder(frame["Close"], 14).iloc[-1] > 0
    assert atr_wilder(frame, 14).iloc[-1] > 0


def test_trade_plan_is_traceable():
    row = analyze_ticker("TEST", make_frame())
    assert row["entry"] == row["price"]
    assert row["stop"] < row["entry"] < row["target"]
    assert row["risk_reward"] > 1
    assert 0 <= row["technical_score"] <= 100
    assert row["methodology"]
