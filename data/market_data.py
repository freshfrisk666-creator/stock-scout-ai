from __future__ import annotations

from typing import Iterable

import pandas as pd
import yfinance as yf


def normalize_ticker(symbol: str) -> str:
    return str(symbol).strip().upper().replace(".", "-").replace("/", "-")


def get_sp500_constituents(source_url: str) -> pd.DataFrame:
    """Fetch the current S&P 500 constituent table from Wikipedia."""
    tables = pd.read_html(source_url)
    if not tables:
        raise RuntimeError("No S&P 500 constituent table found.")
    table = next((t for t in tables if "Symbol" in t.columns), tables[0]).copy()
    table = table.rename(columns={"Symbol": "ticker"})
    table["ticker"] = table["ticker"].map(normalize_ticker)
    return table


def _extract_ticker_frame(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        levels = [raw.columns.get_level_values(i) for i in range(raw.columns.nlevels)]
        if ticker in levels[-1]:
            frame = raw.xs(ticker, axis=1, level=-1, drop_level=True)
        elif ticker in levels[0]:
            frame = raw.xs(ticker, axis=1, level=0, drop_level=True)
        else:
            return pd.DataFrame()
    else:
        frame = raw.copy()
    frame.index = pd.to_datetime(frame.index)
    needed = [c for c in ["Open", "High", "Low", "Close", "Adj Close", "Volume"] if c in frame.columns]
    frame = frame[needed].copy()
    if "Adj Close" not in frame.columns and "Close" in frame.columns:
        frame["Adj Close"] = frame["Close"]
    return frame.dropna(subset=["Close", "Volume"], how="any")


def download_history(
    tickers: Iterable[str],
    period: str = "2y",
    interval: str = "1d",
    batch_size: int = 50,
) -> dict[str, pd.DataFrame]:
    symbols = [normalize_ticker(t) for t in tickers]
    out: dict[str, pd.DataFrame] = {}
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
            frame = _extract_ticker_frame(raw, ticker)
            if not frame.empty:
                out[ticker] = frame
    return out
