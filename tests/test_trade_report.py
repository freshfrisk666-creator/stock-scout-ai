from __future__ import annotations

import pandas as pd

from analysis.trade_report import (
    build_signal_component_report,
    build_signal_summary,
    summarize_trade_performance,
)


def sample_analysis() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "outcome": "WIN",
                "realized_pnl": 100.0,
                "return_pct": 5.0,
                "realized_r_multiple": 2.0,
                "holding_days": 4.0,
                "technical_score": 85.0,
                "trend_score": 90.0,
                "momentum_score": 88.0,
                "rsi_score": 82.0,
                "volume_score": 70.0,
                "breakout_score": 84.0,
            },
            {
                "ticker": "BBB",
                "outcome": "LOSS",
                "realized_pnl": -50.0,
                "return_pct": -2.5,
                "realized_r_multiple": -1.0,
                "holding_days": 2.0,
                "technical_score": 60.0,
                "trend_score": 55.0,
                "momentum_score": 52.0,
                "rsi_score": 65.0,
                "volume_score": 58.0,
                "breakout_score": 40.0,
            },
            {
                "ticker": "CCC",
                "outcome": "FLAT",
                "realized_pnl": 0.0,
                "return_pct": 0.0,
                "realized_r_multiple": 0.0,
                "holding_days": 3.0,
                "technical_score": 70.0,
                "trend_score": 72.0,
                "momentum_score": 69.0,
                "rsi_score": 71.0,
                "volume_score": 66.0,
                "breakout_score": 61.0,
            },
        ]
    )


def test_summarize_performance():
    metrics = summarize_trade_performance(sample_analysis())

    assert metrics["total_trades"] == 3
    assert metrics["wins"] == 1
    assert metrics["losses"] == 1
    assert metrics["flats"] == 1
    assert abs(metrics["win_rate_pct"] - (100.0 / 3.0)) < 1e-9
    assert metrics["total_realized_pnl"] == 50.0
    assert metrics["avg_winner"] == 100.0
    assert metrics["avg_loser"] == -50.0
    assert metrics["profit_factor"] == 2.0
    assert metrics["avg_realized_r_multiple"] == 1.0 / 3.0


def test_signal_component_report_groups_by_outcome():
    report = build_signal_component_report(sample_analysis())

    assert list(report["outcome"]) == ["WIN", "LOSS", "FLAT"]
    assert list(report["trade_count"]) == [1, 1, 1]
    assert report.loc[report["outcome"] == "WIN", "momentum_score"].iloc[0] == 88.0
    assert report.loc[report["outcome"] == "LOSS", "breakout_score"].iloc[0] == 40.0


def test_signal_summary_is_long_form():
    summary = build_signal_summary(sample_analysis())

    assert len(summary) == 18
    assert set(summary["signal"]) == {
        "technical_score",
        "trend_score",
        "momentum_score",
        "rsi_score",
        "volume_score",
        "breakout_score",
    }


def test_empty_inputs_are_safe():
    empty = pd.DataFrame()

    metrics = summarize_trade_performance(empty)
    report = build_signal_component_report(empty)
    summary = build_signal_summary(empty)

    assert metrics["total_trades"] == 0
    assert report.empty
    assert summary.empty
