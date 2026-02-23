from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import requests


@dataclass(frozen=True)
class MoexClient:
    base_url: str
    timeout_s: int = 30

    def get_json(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        resp = requests.get(url, params=params, timeout=self.timeout_s)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _parse_table(payload: Dict[str, Any], table: str) -> List[Dict[str, Any]]:
        data = payload.get(table, {})
        columns = data.get("columns", [])
        rows = data.get("data", [])
        return [dict(zip(columns, row)) for row in rows]

    def get_table(self, path: str, params: Dict[str, Any], table: str) -> List[Dict[str, Any]]:
        payload = self.get_json(path, params)
        return self._parse_table(payload, table)

    def get_table_paged(
        self,
        path: str,
        params: Dict[str, Any],
        table: str,
        page_size: int = 5000,
    ) -> List[Dict[str, Any]]:
        start = 0
        all_rows: List[Dict[str, Any]] = []
        prev_page_signature: tuple[int, str, str] | None = None
        while True:
            page_params = dict(params)
            page_params["start"] = start
            page_params["limit"] = page_size
            payload = self.get_json(path, page_params)
            rows = self._parse_table(payload, table)
            if not rows:
                break

            # Some MOEX endpoints cap page size below requested `limit`.
            # Move by actual page length and guard against repeated pages.
            signature = (len(rows), repr(rows[0]), repr(rows[-1]))
            if signature == prev_page_signature:
                break
            prev_page_signature = signature

            all_rows.extend(rows)
            start += len(rows)
        return all_rows
