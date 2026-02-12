from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from src.moex.futures import FuturesCandlesGateway
from src.storage.sqlite import SQLiteStorage


@dataclass
class CandlesService:
    gateway: FuturesCandlesGateway
    storage: Optional[SQLiteStorage] = None

    def get_hourly_1y(self, ticker: str) -> List[Dict[str, Any]]:
        today = date.today()
        # Use end_date as tomorrow to include latest candles if MOEX treats upper bound as exclusive.
        end_date = today + timedelta(days=1)
        start_date = today - timedelta(days=365)
        rows = self.gateway.fetch_candles(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            interval=60,
        )
        rows = self._filter_rows_up_to_date(rows, today)
        self._persist_if_needed(ticker, 60, rows)
        return rows

    def get_daily_3y(self, ticker: str) -> List[Dict[str, Any]]:
        today = date.today()
        end_date = today + timedelta(days=1)
        start_date = today - timedelta(days=365 * 3)
        rows = self.gateway.fetch_candles(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            interval=24,
        )
        rows = self._filter_rows_up_to_date(rows, today)
        self._persist_if_needed(ticker, 24, rows)
        return rows

    def _persist_if_needed(self, ticker: str, interval: int, rows: List[Dict[str, Any]]) -> None:
        if not self.storage:
            return
        self.storage.init_schema()
        self.storage.upsert_candles(ticker, interval, rows)

    @staticmethod
    def _filter_rows_up_to_date(rows: List[Dict[str, Any]], max_date: date) -> List[Dict[str, Any]]:
        filtered: List[Dict[str, Any]] = []
        for row in rows:
            begin = row.get("begin") or ""
            date_part = begin.split()[0] if begin else ""
            try:
                row_date = date.fromisoformat(date_part)
            except ValueError:
                filtered.append(row)
                continue
            if row_date <= max_date:
                filtered.append(row)
        return filtered
