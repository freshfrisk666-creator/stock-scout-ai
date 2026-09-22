from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def rsi_wilder(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    result = 100 - (100 / (1 + rs))
    result = result.mask(avg_loss.eq(0) & avg_gain.gt(0), 100.0)
    return result.fillna(50.0)


def atr_wilder(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    previous_close = frame["Close"].shift(1)
    true_range = pd.concat(
        [
            frame["High"] - frame["Low"],
            (frame["High"] - previous_close).abs(),
            (frame["Low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def _score_rsi(value: float) -> float:
    if 55 <= value <= 68:
        return 100.0
    if 50 <= value < 55 or 68 < value <= 72:
        return 70.0
    if 45 <= value < 50 or 72 < value <= 78:
        return 45.0
    return 20.0


def analyze_ticker(
    ticker: str,
    frame: pd.DataFrame,
    sma_fast: int = 20,
    sma_mid: int = 50,
    sma_slow: int = 200,
    rsi_period: int = 14,
    atr_period: int = 14,
    momentum_short: int = 21,
    momentum_long: int = 63,
    breakout_window: int = 20,
    volume_window: int = 20,
    stop_atr_multiple: float = 1.5,
    target_atr_multiple: float = 3.0,
) -> dict:
    """M2: transparent technical features, score, and trade plan."""
    minimum = max(sma_slow, momentum_long, breakout_window, volume_window) + 5
    if len(frame) < minimum:
        raise ValueError(f"{ticker}: insufficient history")

    close = frame["Close"]
    volume = frame["Volume"]
    sma20 = sma(close, sma_fast)
    sma50 = sma(close, sma_mid)
    sma200 = sma(close, sma_slow)
    rsi = rsi_wilder(close, rsi_period)
    atr = atr_wilder(frame, atr_period)

    price = float(close.iloc[-1])
    v_sma20 = float(sma20.iloc[-1])
    v_sma50 = float(sma50.iloc[-1])
    v_sma200 = float(sma200.iloc[-1])
    v_rsi = float(rsi.iloc[-1])
    v_atr = float(atr.iloc[-1])
    mom21 = price / float(close.iloc[-momentum_short - 1]) - 1
    mom63 = price / float(close.iloc[-momentum_long - 1]) - 1
    avg_volume = float(volume.rolling(volume_window).mean().iloc[-1])
    volume_ratio = float(volume.iloc[-1] / avg_volume) if avg_volume else 0.0
    prior_high = float(close.rolling(breakout_window).max().iloc[-2])
    breakout_strength = price / prior_high - 1 if prior_high else 0.0

    trend_score = 25 * sum([
        price > v_sma20,
        v_sma20 > v_sma50,
        v_sma50 > v_sma200,
        price > v_sma200,
    ])
    momentum_score = float(
        0.55 * np.clip(50 + mom21 * 250, 0, 100)
        + 0.45 * np.clip(50 + mom63 * 150, 0, 100)
    )
    rsi_score = _score_rsi(v_rsi)
    volume_score = float(np.clip(50 + (volume_ratio - 1) * 80, 0, 100))
    breakout_score = float(np.clip(50 + breakout_strength * 1000, 0, 100))
    technical_score = (
        0.30 * trend_score
        + 0.25 * momentum_score
        + 0.15 * rsi_score
        + 0.15 * volume_score
        + 0.15 * breakout_score
    )

    entry = price
    stop = entry - stop_atr_multiple * v_atr
    target = entry + target_atr_multiple * v_atr
    risk = max(entry - stop, 1e-9)
    reward = target - entry

    return {
        "ticker": ticker,
        "date": frame.index[-1],
        "price": entry,
        "sma20": v_sma20,
        "sma50": v_sma50,
        "sma200": v_sma200,
        "rsi14": v_rsi,
        "atr14": v_atr,
        "momentum_21d": mom21,
        "momentum_63d": mom63,
        "volume_ratio_20d": volume_ratio,
        "breakout_strength_20d": breakout_strength,
        "trend_score": trend_score,
        "momentum_score": momentum_score,
        "rsi_score": rsi_score,
        "volume_score": volume_score,
        "breakout_score": breakout_score,
        "technical_score": technical_score,
        "entry": entry,
        "stop": stop,
        "target": target,
        "risk_reward": reward / risk,
        "methodology": "trend30 + momentum25 + rsi15 + volume15 + breakout15; stop=1.5*ATR14; target=3*ATR14",
    }


def analyze_candidates(scan: pd.DataFrame, history: Dict[str, pd.DataFrame], **kwargs) -> pd.DataFrame:
    rows = []
    for ticker in scan.get("ticker", pd.Series(dtype=str)).tolist():
        frame = history.get(ticker)
        if frame is None or frame.empty:
            continue
        try:
            rows.append(analyze_ticker(ticker, frame, **kwargs))
        except ValueError:
            continue
    return pd.DataFrame(rows).sort_values("technical_score", ascending=False).reset_index(drop=True) if rows else pd.DataFrame()
