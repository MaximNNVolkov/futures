from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

import sqlite3


@dataclass
class SQLiteStorage:
    db_path: Path

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS candles (
                    ticker TEXT NOT NULL,
                    interval INTEGER NOT NULL,
                    begin TEXT NOT NULL,
                    end TEXT NOT NULL,
                    open REAL,
                    close REAL,
                    high REAL,
                    low REAL,
                    value REAL,
                    volume REAL,
                    openposition REAL,
                    PRIMARY KEY (ticker, interval, begin)
                )
                """
            )

    def upsert_candles(self, ticker: str, interval: int, rows: Iterable[Dict[str, Any]]) -> int:
        rows_list = list(rows)
        if not rows_list:
            return 0
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO candles (
                    ticker, interval, begin, end, open, close, high, low,
                    value, volume, openposition
                ) VALUES (
                    :ticker, :interval, :begin, :end, :open, :close, :high, :low,
                    :value, :volume, :openposition
                )
                """,
                [
                    {
                        "ticker": ticker,
                        "interval": interval,
                        "begin": row.get("begin"),
                        "end": row.get("end"),
                        "open": row.get("open"),
                        "close": row.get("close"),
                        "high": row.get("high"),
                        "low": row.get("low"),
                        "value": row.get("value"),
                        "volume": row.get("volume"),
                        "openposition": row.get("openposition"),
                    }
                    for row in rows_list
                ],
            )
        return len(rows_list)

