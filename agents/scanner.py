from __future__ import annotations

from typing import Optional

import pandas as pd

from data.market_data import download_history, get_sp500_constituents


def run_scan(
    source_url: str,
    min_price: float | None = None,
    min_avg_dollar_volume_20d: float = 50_000_000,
    period: str = "2y",
    interval: str = "1d",
    batch_size: int = 50,
    max_symbols: Optional[int] = None,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Fetch the S&P 500 universe and apply liquidity/history filters.

    ``min_price`` is retained for backward compatibility with existing callers,
    but when it is ``None`` no minimum share-price filter is applied.
    The default is therefore to consider stocks at any positive market price,
    subject only to the history and liquidity checks below.
    """
    constituents = get_sp500_constituents(source_url)
    symbols = constituents["ticker"].tolist()

    if max_symbols:
        symbols = symbols[:max_symbols]

    history = download_history(
        symbols,
        period=period,
        interval=interval,
        batch_size=batch_size,
    )

    rows: list[dict] = []

    for ticker, frame in history.items():
        if len(frame) < 220:
            continue

        price = float(frame["Close"].iloc[-1])
        adv20 = float(
            (frame["Close"] * frame["Volume"]).tail(20).mean()
        )

        price_ok = min_price is None or price >= float(min_price)
        liquidity_ok = adv20 >= min_avg_dollar_volume_20d

        if price_ok and liquidity_ok:
            rows.append(
                {
                    "ticker": ticker,
                    "date": frame.index[-1],
                    "price": price,
                    "avg_dollar_volume_20d": adv20,
                }
            )

    scan = pd.DataFrame(rows)

    if scan.empty:
        return scan, history

    return (
        scan.sort_values(
            ["avg_dollar_volume_20d", "ticker"],
            ascending=[False, True],
        ).reset_index(drop=True),
        history,
    )
