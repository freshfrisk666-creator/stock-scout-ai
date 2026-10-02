import pandas as pd

from analysis.mfe_mae_tp import (
    resolve_ambiguous,
    run_exit_strategy_study,
    simulate_exit_policy,
)


def position():
    return pd.Series(
        {
            "id": 1,
            "ticker": "TEST",
            "entry_date": "2026-10-01T13:30:00+00:00",
            "entry_price": 100.0,
            "stop": 95.0,
            "target": 115.0,
            "status": "CLOSED",
            "exit_date": "2026-10-05T20:00:00+00:00",
            "exit_price": 95.0,
        }
    )


def test_tp_target():
    bars = pd.DataFrame(
        {"High": [104, 106], "Low": [99, 101], "Close": [103, 105]},
        index=pd.to_datetime(["2026-10-01", "2026-10-02"]),
    )
    result = simulate_exit_policy(position(), 1.0, bars)
    assert result["result"] == "TARGET"
    assert result["realized_r"] == 1.0


def test_ambiguous_resolution():
    bars = pd.DataFrame(
        {"High": [111], "Low": [94], "Close": [100]},
        index=pd.to_datetime(["2026-10-01"]),
    )
    result = simulate_exit_policy(position(), 1.0, bars)
    assert result["result"] == "AMBIGUOUS"
    assert resolve_ambiguous(result["result"], 1.0, "conservative") == ("STOP", -1.0)
    assert resolve_ambiguous(result["result"], 1.0, "optimistic") == ("TARGET", 1.0)


def test_breakeven_next_bar():
    bars = pd.DataFrame(
        {"High": [104, 103], "Low": [99, 98], "Close": [104, 98]},
        index=pd.to_datetime(["2026-10-01", "2026-10-02"]),
    )
    result = simulate_exit_policy(position(), 3.0, bars, breakeven_trigger_r=0.75)
    assert result["result"] == "BREAKEVEN"
    assert result["realized_r"] == 0.0


def test_study_has_all_scenarios():
    positions = pd.DataFrame([position().to_dict()])
    bars = pd.DataFrame(
        {"High": [104, 104], "Low": [99, 94], "Close": [104, 98]},
        index=pd.to_datetime(["2026-10-01", "2026-10-02"]),
    )

    def downloader(ticker, start, end):
        return bars

    by_trade, summary = run_exit_strategy_study(
        positions, pd.Timestamp("2026-10-02"), downloader
    )
    assert len(summary) == 9
    assert "BE_0.75R_THEN_TP_3R" in set(summary["strategy"])
