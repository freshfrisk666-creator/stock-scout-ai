from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


def get_connection(db_path: str = "data/stock_scout.db") -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path)


def save_dataframe(frame: pd.DataFrame, table_name: str, db_path: str = "data/stock_scout.db") -> None:
    if frame is None or frame.empty:
        return
    with get_connection(db_path) as conn:
        frame.to_sql(table_name, conn, if_exists="append", index=False)
