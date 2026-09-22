from __future__ import annotations

from io import StringIO
from dataclasses import dataclass
from typing import Iterable

import pandas as pd
import requests
import yfinance as yf


@dataclass(frozen=True)
class MarketConfig:
    history_period: str = "2y"
    interval: str = "1d"
    batch_size: int = 50


WIKIPEDIA_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    )
}


def normalize_ticker(symbol: str) -> str:
    """Convert an S&P 500-style symbol to Yahoo Finance format."""
    return str(symbol).strip().upper().replace(".", "-").replace("/", "-")


def get_sp500_constituents(source_url: str) -> pd.DataFrame:
    """Fetch the current S&P 500 constituent table robustly."""
    response = requests.get(source_url, headers=WIKIPEDIA_HEADERS, timeout=30)
    response.raise_for_status()

    tables = pd.read_html(StringIO(response.text))
    if not tables:
        raise RuntimeError("No constituent tables were found.")

    table = next((t for t in tables if "Symbol" in t.columns), None)
    if table is None:
        raise RuntimeError("Could not find an S&P 500 table containing a Symbol column.")

    table = table.rename(columns={"Symbol": "ticker"})
    table["ticker"] = table["ticker"].map(normalize_ticker)
    return table


def _extract_download_frame(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Normalize yfinance's single- or multi-ticker result to OHLCV columns."""
    if raw is None or raw.empty:
        return pd.DataFrame()

    expected = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]

    if isinstance(raw.columns, pd.MultiIndex):
        if ticker in raw.columns.get_level_values(-1):
            frame = raw.xs(ticker, axis=1, level=-1, drop_level=True)
        elif ticker in raw.columns.get_level_values(0):
            frame = raw.xs(ticker, axis=1, level=0, drop_level=True)
        else:
            return pd.DataFrame()
    else:
        frame = raw.copy()

    frame = frame.rename(columns={c: str(c) for c in frame.columns})

    if "Adj Close" not in frame.columns and "Close" in frame.columns:
        frame["Adj Close"] = frame["Close"]

    frame = frame[[c for c in expected if c in frame.columns]].copy()
    frame.index = pd.to_datetime(frame.index)

    return frame.dropna(subset=["Close", "Volume"], how="any")


def download_history(
    tickers: Iterable[str],
    period: str = "2y",
    interval: str = "1d",
    batch_size: int = 50,
) -> dict[str, pd.DataFrame]:
    """Download market history in batches."""
    symbols = [normalize_ticker(x) for x in tickers]
    output: dict[str, pd.DataFrame] = {}

    for start in range(0, len(symbols), batch_size):
        batch = symbols[start : start + batch_size]

        raw = yf.download(
            tickers=batch,
            period=period,
            interval=interval,
            auto_adjust=False,
            progress=False,
            threads=True,
            group_by="column",
            multi_level_index=True,
            timeout=20,
        )

        for ticker in batch:
            frame = _extract_download_frame(raw, ticker)
            if not frame.empty:
                output[ticker] = frame

    return output
