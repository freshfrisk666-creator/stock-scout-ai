from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf


DB_PATH = "data/stock_scout.db"
OUTPUT_DIR = Path("dashboard/trades")
HISTORY_PERIOD = "2y"
LOOKBACK_DAYS = 420
AFTER_TRADE_DAYS = 20
PIVOT_WINDOW = 3
LEVEL_TOLERANCE = 0.015
DIVERGENCE_PIVOT_WINDOW = 3
DIVERGENCE_MAX_GAP_SESSIONS = 60
DIVERGENCE_PRICE_THRESHOLD = 0.01
DIVERGENCE_RSI_THRESHOLD = 2.0
DIVERGENCE_LOOKBACK_DAYS = 180


def clean(value):
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if hasattr(value, "item"):
        try:
            value = value.item()
        except (AttributeError, ValueError):
            pass

    if isinstance(value, float) and not math.isfinite(value):
        return None

    return value


def as_float(value):
    value = clean(value)
    return None if value is None else float(value)


def to_naive_timestamp(value):
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts.normalize()


def frame_for_symbol(data: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if data is None or data.empty:
        return pd.DataFrame()

    try:
        if isinstance(data.columns, pd.MultiIndex):
            level0 = list(data.columns.get_level_values(0))
            level1 = list(data.columns.get_level_values(1))

            if symbol in level0:
                frame = data[symbol].copy()
            elif symbol in level1:
                frame = data.xs(symbol, axis=1, level=1).copy()
            else:
                return pd.DataFrame()
        else:
            frame = data.copy()

        frame.columns = [str(c).lower() for c in frame.columns]

        for column in ["open", "high", "low", "close", "volume"]:
            if column not in frame.columns:
                frame[column] = None

        frame = frame[["open", "high", "low", "close", "volume"]].copy()
        frame.index = pd.to_datetime(frame.index, errors="coerce")

        if getattr(frame.index, "tz", None) is not None:
            frame.index = frame.index.tz_convert("UTC").tz_localize(None)

        frame = frame[~frame.index.isna()].sort_index()
        frame = frame[~frame.index.duplicated(keep="last")]
        frame = frame.dropna(subset=["open", "high", "low", "close"])

        return frame

    except Exception:
        return pd.DataFrame()


def wilder_rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    avg_gain = gain.ewm(
        alpha=1.0 / window,
        adjust=False,
        min_periods=window,
    ).mean()

    avg_loss = loss.ewm(
        alpha=1.0 / window,
        adjust=False,
        min_periods=window,
    ).mean()

    rs = avg_gain / avg_loss.replace(0, pd.NA)
    rsi = 100.0 - (100.0 / (1.0 + rs))

    rsi = rsi.where(~((avg_loss == 0) & (avg_gain > 0)), 100.0)
    rsi = rsi.where(~((avg_gain == 0) & (avg_loss > 0)), 0.0)

    return rsi.astype(float)


def wilder_atr(frame: pd.DataFrame, window: int = 14) -> pd.Series:
    previous_close = frame["close"].shift(1)

    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return true_range.ewm(
        alpha=1.0 / window,
        adjust=False,
        min_periods=window,
    ).mean()


def add_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    close = result["close"]

    result["sma20"] = close.rolling(20).mean()
    result["sma50"] = close.rolling(50).mean()
    result["sma200"] = close.rolling(200).mean()
    result["rsi14"] = wilder_rsi(close, 14)
    result["atr14"] = wilder_atr(result, 14)
    result["volume_avg20"] = result["volume"].rolling(20).mean()
    result["volume_ratio"] = (
        result["volume"] / result["volume_avg20"].replace(0, pd.NA)
    )
    result["breakout_strength_20d"] = (
        close / close.shift(1).rolling(20).max() - 1.0
    )

    return result


def nearest_trade_date(index, target):
    if index.empty or target is None:
        return None

    target = to_naive_timestamp(target)
    eligible = index[index <= target]

    if len(eligible) == 0:
        return index[0]

    return eligible[-1]


def pivot_levels(frame: pd.DataFrame, kind: str) -> list[float]:
    if len(frame) < (PIVOT_WINDOW * 2 + 1):
        return []

    column = "low" if kind == "support" else "high"
    values = frame[column]
    levels = []

    for i in range(PIVOT_WINDOW, len(frame) - PIVOT_WINDOW):
        window = values.iloc[i - PIVOT_WINDOW:i + PIVOT_WINDOW + 1]
        current = float(values.iloc[i])

        if kind == "support" and current <= float(window.min()):
            levels.append(current)

        if kind == "resistance" and current >= float(window.max()):
            levels.append(current)

    return levels


def clustered_level_ranges(levels: list[float]) -> list[dict]:
    if not levels:
        return []

    sorted_levels = sorted(
        float(level) for level in levels if math.isfinite(float(level))
    )

    clusters = []

    for level in sorted_levels:
        if not clusters:
            clusters.append([level])
            continue

        current = clusters[-1]
        anchor = sum(current) / len(current)

        if anchor and abs(level - anchor) / anchor <= LEVEL_TOLERANCE:
            current.append(level)
        else:
            clusters.append([level])

    result = []

    for cluster in clusters:
        result.append({
            "low": min(cluster),
            "high": max(cluster),
            "mid": sum(cluster) / len(cluster),
            "touches": len(cluster),
        })

    return result


def context_zones(frame: pd.DataFrame, entry_price: float) -> list[dict]:
    recent = frame.tail(160)

    supports = clustered_level_ranges(pivot_levels(recent, "support"))
    resistances = clustered_level_ranges(pivot_levels(recent, "resistance"))

    below = sorted(
        [zone for zone in supports if zone["mid"] < entry_price],
        key=lambda zone: entry_price - zone["mid"],
    )[:1]

    above = sorted(
        [zone for zone in resistances if zone["mid"] > entry_price],
        key=lambda zone: zone["mid"] - entry_price,
    )[:1]

    result = []

    entry_atr = None
    if "atr14" in frame.columns:
        atr_series = frame["atr14"].dropna()
        if not atr_series.empty:
            entry_atr = float(atr_series.iloc[-1])

    # A single pivot can produce low == high, which would otherwise render as
    # a 1-pixel line. Give the zone a small visual thickness while preserving
    # the actual min/max range whenever the cluster contains multiple pivots.
    visual_pad = max(
        (entry_atr * 0.35) if entry_atr and math.isfinite(entry_atr) else 0.0,
        float(entry_price) * 0.0025,
    )

    def visual_bounds(zone):
        low = float(zone["low"])
        high = float(zone["high"])
        if (high - low) < visual_pad:
            mid = float(zone["mid"])
            low = mid - (visual_pad / 2.0)
            high = mid + (visual_pad / 2.0)
        return round(low, 6), round(high, 6)

    for zone in below:
        low, high = visual_bounds(zone)
        result.append({
            "kind": "support",
            "low": low,
            "high": high,
            "mid": round(zone["mid"], 6),
            "touches": int(zone["touches"]),
        })

    for zone in above:
        low, high = visual_bounds(zone)
        result.append({
            "kind": "resistance",
            "low": low,
            "high": high,
            "mid": round(zone["mid"], 6),
            "touches": int(zone["touches"]),
        })

    return result


def divergence_pivots(frame: pd.DataFrame, kind: str) -> list[tuple[pd.Timestamp, float, float]]:
    column = "low" if kind == "bullish" else "high"
    values = frame[column]
    result = []
    window = DIVERGENCE_PIVOT_WINDOW

    if len(frame) < (window * 2 + 1):
        return result

    for i in range(window, len(frame) - window):
        ts = frame.index[i]
        value = values.iloc[i]
        rsi = frame["rsi14"].iloc[i]

        if pd.isna(value) or pd.isna(rsi):
            continue

        local = values.iloc[i - window:i + window + 1]

        if kind == "bullish" and float(value) <= float(local.min()):
            result.append((ts, float(value), float(rsi)))

        if kind == "bearish" and float(value) >= float(local.max()):
            result.append((ts, float(value), float(rsi)))

    return result


def detect_rsi_divergences(frame: pd.DataFrame, entry_bar, end_bar) -> list[dict]:
    if frame.empty or "rsi14" not in frame.columns:
        return []

    analysis_start = entry_bar - pd.Timedelta(days=DIVERGENCE_LOOKBACK_DAYS)
    analysis_end = end_bar + pd.Timedelta(days=AFTER_TRADE_DAYS)
    window = frame.loc[
        (frame.index >= analysis_start)
        & (frame.index <= analysis_end)
    ].copy()

    result = []

    for kind in ("bullish", "bearish"):
        pivots = divergence_pivots(window, kind)

        for previous, current in zip(pivots[:-1], pivots[1:]):
            prev_time, prev_price, prev_rsi = previous
            cur_time, cur_price, cur_rsi = current

            gap_sessions = len(
                window.loc[(window.index >= prev_time) & (window.index <= cur_time)]
            ) - 1

            if gap_sessions < 2 or gap_sessions > DIVERGENCE_MAX_GAP_SESSIONS:
                continue

            if kind == "bullish":
                price_condition = cur_price <= prev_price * (1.0 - DIVERGENCE_PRICE_THRESHOLD)
                rsi_condition = cur_rsi >= prev_rsi + DIVERGENCE_RSI_THRESHOLD
            else:
                price_condition = cur_price >= prev_price * (1.0 + DIVERGENCE_PRICE_THRESHOLD)
                rsi_condition = cur_rsi <= prev_rsi - DIVERGENCE_RSI_THRESHOLD

            if not (price_condition and rsi_condition):
                continue

            result.append({
                "type": kind,
                "start_time": int(prev_time.timestamp()),
                "end_time": int(cur_time.timestamp()),
                "start_date": prev_time.strftime("%Y-%m-%d"),
                "end_date": cur_time.strftime("%Y-%m-%d"),
                "start_price": round(prev_price, 6),
                "end_price": round(cur_price, 6),
                "start_rsi": round(prev_rsi, 4),
                "end_rsi": round(cur_rsi, 4),
                "gap_sessions": gap_sessions,
            })

    result.sort(key=lambda item: (item["end_time"], item["type"]))

    # Keep the panel readable: latest three signals of each type are enough
    # for a trade-level diagnostic without turning the RSI pane into spaghetti.
    filtered = []
    for kind in ("bullish", "bearish"):
        typed = [item for item in result if item["type"] == kind]
        filtered.extend(typed[-3:])

    return sorted(filtered, key=lambda item: item["end_time"])


def trendline_from_pivots(frame: pd.DataFrame, kind: str, end_time) -> dict | None:
    recent = frame.tail(180)

    if len(recent) < (PIVOT_WINDOW * 2 + 1):
        return None

    column = "low" if kind == "support" else "high"
    values = recent[column]
    pivots = []

    for i in range(PIVOT_WINDOW, len(recent) - PIVOT_WINDOW):
        window = values.iloc[i - PIVOT_WINDOW:i + PIVOT_WINDOW + 1]
        value = float(values.iloc[i])

        is_pivot = (
            kind == "support" and value <= float(window.min())
        ) or (
            kind == "resistance" and value >= float(window.max())
        )

        if is_pivot:
            pivots.append((recent.index[i], value))

    if len(pivots) < 2:
        return None

    for i in range(max(0, len(pivots) - 8), len(pivots) - 1):
        t1, p1 = pivots[i]

        for j in range(i + 1, len(pivots)):
            t2, p2 = pivots[j]

            if t2 <= t1:
                continue

            relative_move = abs(p2 - p1) / max(abs(p1), 1e-9)
            if relative_move < 0.02:
                continue

            slope = (p2 - p1) / max(
                1.0,
                (t2 - t1).total_seconds() / 86400,
            )

            days_forward = max(
                1.0,
                (end_time - t2).total_seconds() / 86400,
            )

            return {
                "kind": kind,
                "start": {
                    "time": int(t1.timestamp()),
                    "price": float(p1),
                },
                "end": {
                    "time": int(end_time.timestamp()),
                    "price": float(p2 + slope * days_forward),
                },
            }

    return None


def vix_value_at(vix: pd.Series, target):
    if vix.empty:
        return None

    target = to_naive_timestamp(target)
    subset = vix.loc[vix.index <= target]

    if subset.empty:
        return None

    return as_float(subset.iloc[-1])


def vix_change(vix: pd.Series, target, periods: int):
    if vix.empty:
        return None

    target = to_naive_timestamp(target)
    subset = vix.loc[vix.index <= target]

    if len(subset) <= periods:
        return None

    current = as_float(subset.iloc[-1])
    previous = as_float(subset.iloc[-1 - periods])

    if current is None or previous in (None, 0):
        return None

    return (current / previous - 1.0) * 100.0


def build_vix_context(vix_frame, entry_date, end_date):
    if vix_frame.empty:
        return {
            "available": False,
            "entry": None,
            "average": None,
            "exit": None,
            "change_pct": None,
            "change_5d_pct": None,
            "change_20d_pct": None,
        }

    series = vix_frame["close"].dropna()

    entry_value = vix_value_at(series, entry_date)
    exit_value = vix_value_at(series, end_date)

    trade_slice = series.loc[
        (series.index >= entry_date)
        & (series.index <= end_date)
    ]

    average = (
        float(trade_slice.mean())
        if not trade_slice.empty
        else None
    )

    change_pct = None
    if entry_value not in (None, 0) and exit_value is not None:
        change_pct = (exit_value / entry_value - 1.0) * 100.0

    return {
        "available": True,
        "entry": entry_value,
        "average": average,
        "exit": exit_value,
        "change_pct": change_pct,
        "change_5d_pct": vix_change(series, entry_date, 5),
        "change_20d_pct": vix_change(series, entry_date, 20),
    }


def snapshot(raw):
    if not raw:
        return {}

    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}


def serialize_bars(frame):
    result = []

    for timestamp, row in frame.iterrows():
        item = {
            "time": int(timestamp.timestamp()),
            "date": timestamp.strftime("%Y-%m-%d"),
            "open": as_float(row["open"]),
            "high": as_float(row["high"]),
            "low": as_float(row["low"]),
            "close": as_float(row["close"]),
            "volume": as_float(row["volume"]),
            "sma20": as_float(row["sma20"]),
            "sma50": as_float(row["sma50"]),
            "sma200": as_float(row["sma200"]),
            "rsi14": as_float(row["rsi14"]),
            "atr14": as_float(row["atr14"]),
            "volume_ratio": as_float(row["volume_ratio"]),
            "breakout_strength_20d": as_float(row["breakout_strength_20d"]),
        }

        if item["open"] is None or item["close"] is None:
            continue

        result.append(item)

    return result


def build_trade(row, frames, vix_frame):
    ticker = str(row["ticker"])
    raw = frames.get(ticker, pd.DataFrame())

    if raw.empty:
        raise ValueError("Historical data not available")

    frame = add_indicators(raw)

    entry_date = to_naive_timestamp(row["entry_date"])

    if clean(row["exit_date"]):
        end_date = to_naive_timestamp(row["exit_date"])
    else:
        end_date = frame.index[-1]

    entry_bar = nearest_trade_date(frame.index, entry_date)
    end_bar = nearest_trade_date(frame.index, end_date)

    if entry_bar is None:
        raise ValueError("Entry date is outside available history")

    if end_bar is None:
        end_bar = frame.index[-1]

    start = entry_bar - pd.Timedelta(days=LOOKBACK_DAYS)
    stop = end_bar + pd.Timedelta(days=AFTER_TRADE_DAYS)

    chart_frame = frame.loc[
        (frame.index >= start)
        & (frame.index <= stop)
    ].copy()

    entry_context = chart_frame.loc[
        chart_frame.index <= entry_bar
    ]

    signal = snapshot(row["signal_snapshot"])

    exit_price = clean(row["exit_price"])
    realized_pnl = clean(row["realized_pnl"])

    realized_return = None
    if exit_price is not None and float(row["entry_price"]) != 0:
        realized_return = (
            (float(exit_price) - float(row["entry_price"]))
            / float(row["entry_price"])
        ) * 100.0

    trendlines = []

    support_line = trendline_from_pivots(
        entry_context,
        "support",
        chart_frame.index[-1],
    )

    resistance_line = trendline_from_pivots(
        entry_context,
        "resistance",
        chart_frame.index[-1],
    )

    if support_line:
        trendlines.append(support_line)

    if resistance_line:
        trendlines.append(resistance_line)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "id": int(row["id"]),
        "ticker": ticker,
        "status": str(row["status"]),
        "strategy_type": clean(row["strategy_type"]) or "SWING",
        "rank": clean(row["rank"]),
        "entry_date": str(row["entry_date"]),
        "exit_date": clean(row["exit_date"]),
        "entry_bar_date": entry_bar.strftime("%Y-%m-%d"),
        "exit_bar_date": end_bar.strftime("%Y-%m-%d"),
        "entry_price": float(row["entry_price"]),
        "entry_time": int(entry_bar.timestamp()),
        "trade_end_time": int(end_bar.timestamp()),
        "exit_price": float(exit_price) if exit_price is not None else None,
        "shares": int(row["shares"]),
        "notional": float(row["notional"]),
        "stop": float(row["stop"]),
        "target": float(row["target"]),
        "realized_pnl": float(realized_pnl) if realized_pnl is not None else None,
        "realized_return_pct": realized_return,
        "close_reason": clean(row["close_reason"]),
        "planned_horizon_sessions": (
            int(row["planned_horizon_sessions"])
            if clean(row["planned_horizon_sessions"])
            else 20
        ),
        "signal": {
            key: clean(signal.get(key))
            for key in [
                "technical_score",
                "trend_score",
                "momentum_score",
                "rsi_score",
                "volume_score",
                "breakout_score",
                "risk_reward",
            ]
        },
        "methodology": clean(signal.get("methodology")),
        "vix_context": build_vix_context(
            vix_frame,
            entry_bar,
            end_bar,
        ),
        "zones": context_zones(
            entry_context,
            float(row["entry_price"]),
        ),
        "trendlines": trendlines,
        "divergences": detect_rsi_divergences(
            frame,
            entry_bar,
            end_bar,
        ),
        "bars": serialize_bars(chart_frame),
    }


def download_history(tickers):
    symbols = sorted(set(tickers + ["^VIX"]))

    data = yf.download(
        tickers=symbols,
        period=HISTORY_PERIOD,
        interval="1d",
        auto_adjust=False,
        group_by="ticker",
        progress=False,
        threads=False,
    )

    frames = {
        ticker: frame_for_symbol(data, ticker)
        for ticker in tickers
    }

    return frames, frame_for_symbol(data, "^VIX")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for path in OUTPUT_DIR.glob("*.json"):
        path.unlink()

    with sqlite3.connect(DB_PATH) as conn:
        positions = pd.read_sql_query(
            """
            SELECT
                id,
                ticker,
                rank,
                entry_date,
                entry_price,
                shares,
                notional,
                stop,
                target,
                status,
                signal_snapshot,
                exit_date,
                exit_price,
                realized_pnl,
                close_reason,
                strategy_type,
                planned_horizon_sessions
            FROM positions
            WHERE portfolio_id = 'default'
            ORDER BY id ASC
            """,
            conn,
        )

    if positions.empty:
        print("No portfolio positions found; no trade charts generated.")
        return

    tickers = positions["ticker"].astype(str).unique().tolist()
    frames, vix_frame = download_history(tickers)

    count = 0

    for _, row in positions.iterrows():
        trade_id = int(row["id"])

        try:
            payload = build_trade(
                row,
                frames,
                vix_frame,
            )
        except Exception as exc:
            payload = {
                "id": trade_id,
                "ticker": str(row["ticker"]),
                "status": str(row["status"]),
                "error": str(exc),
            }

        with (OUTPUT_DIR / f"{trade_id}.json").open(
            "w",
            encoding="utf-8",
        ) as handle:
            json.dump(
                payload,
                handle,
                ensure_ascii=False,
                indent=2,
                default=clean,
            )

        count += 1

    with (OUTPUT_DIR / "index.json").open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "count": count,
                "interval": "1d",
                "data_source": "Yahoo Finance via yfinance",
                "vix_symbol": "^VIX",
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )

    print(
        f"Trade chart data written: {count} trades -> {OUTPUT_DIR.as_posix()}"
    )


if __name__ == "__main__":
    main()
