from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List

from .client import MoexClient


@dataclass(frozen=True)
class FuturesCandlesGateway:
    client: MoexClient

    def fetch_candles(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
        interval: int,
    ) -> List[Dict[str, Any]]:
        # MOEX ISS candles: interval in minutes (1, 10, 60) or 24 for daily
        path = f"engines/futures/markets/forts/securities/{ticker}/candles.json"
        params = {
            "from": start_date.isoformat(),
            "to": end_date.isoformat(),
            "till": end_date.isoformat(),
            "interval": interval,
            "iss.meta": "off",
            "iss.only": "candles",
        }
        return self.client.get_table_paged(path, params, table="candles")
