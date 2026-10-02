import pandas as pd
from analysis_mfe_mae_tp import (
    build_mfe_mae_analysis,
    resolve_ambiguous,
    simulate_tp_for_trade,
)


def make_position(status="CLOSED", exit_date="2026-10-02T20:00:00+00:00"):
    return pd.Series({
        "id": 1,
        "ticker": "TEST",
        "entry_date": "2026-10-01T13:30:00+00:00",
        "entry_price": 100.0,
        "stop": 95.0,
        "target": 110.0,
        "status": status,
        "exit_date": exit_date,
        "exit_price": 95.0 if status == "CLOSED" else None,
    })


def test_tp_target():
    bars = pd.DataFrame(
        {"High": [102, 106], "Low": [99, 101], "Close": [101, 105]},
        index=pd.to_datetime(["2026-10-01", "2026-10-02"]),
    )
    result = simulate_tp_for_trade(make_position(), 1.0, bars)
    assert result[0] == "TARGET"
    assert result[1] == 1.0


def test_tp_ambiguous():
    bars = pd.DataFrame(
        {"High": [111], "Low": [94], "Close": [100]},
        index=pd.to_datetime(["2026-10-01"]),
    )
    result = simulate_tp_for_trade(make_position(), 1.0, bars)
    assert result[0] == "AMBIGUOUS"
    assert resolve_ambiguous(result[0], 1.0, "conservative") == ("STOP", -1.0)
    assert resolve_ambiguous(result[0], 1.0, "optimistic") == ("TARGET", 1.0)


def test_mfe_mae():
    positions = pd.DataFrame([make_position(status="OPEN", exit_date=None).to_dict()])
    bars = pd.DataFrame(
        {"High": [103, 110], "Low": [98, 99], "Close": [102, 105]},
        index=pd.to_datetime(["2026-10-01", "2026-10-02"]),
    )

    def downloader(ticker, start, end):
        return bars

    result, cache = build_mfe_mae_analysis(
        positions,
        portfolio_marks={"TEST": 105.0},
        today_ny=pd.Timestamp("2026-10-02"),
        downloader=downloader,
    )
    assert len(result) == 1
    assert abs(result.iloc[0]["mfe_R"] - 2.0) < 1e-9
    assert abs(result.iloc[0]["mae_R"] - 0.4) < 1e-9
    assert abs(result.iloc[0]["current_R"] - 1.0) < 1e-9
