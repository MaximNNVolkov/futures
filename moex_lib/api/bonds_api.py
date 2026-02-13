import requests

class BondsApi:
    BASE_URL = "https://iss.moex.com/iss"
    REQUEST_TIMEOUT_SECONDS = 15

    def __init__(self):
        self._amortization_cache = {}

    def get_bonds(self) -> dict:
        url = f"{self.BASE_URL}/engines/stock/markets/bonds/securities.json"
        params = {
            "iss.meta": "off",
            "iss.only": "securities,marketdata",
            "securities.columns": ",".join(
                [
                    "SECID",
                    "SHORTNAME",
                    "MATDATE",
                    "COUPONFREQUENCY",
                    "COUPONPERIOD",
                    "COUPONPERCENT",
                    "COUPONVALUE",
                    "FACEUNIT",
                    "FACEVALUE",
                    "ISSUERTYPE",
                    "BONDTYPE",
                    "COUPONTYPE",
                    "AMORTIZATION",
                    "OFFERDATE",
                    "SECTYPE",
                    "TYPE",
                    "TYPENAME",
                    "GROUP",
                    "GROUPNAME",
                ]
            ),
        }
        resp = requests.get(url, params=params, timeout=self.REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        return resp.json()

    def get_amortizations(self, secid: str) -> dict:
        cached = self._amortization_cache.get(secid)
        if cached is not None:
            return cached
        url = f"{self.BASE_URL}/securities/{secid}/bondization.json"
        params = {
            "iss.meta": "off",
            "iss.only": "amortizations",
        }
        resp = requests.get(url, params=params, timeout=self.REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        data = resp.json()
        amort = data.get("amortizations") or {}
        columns = amort.get("columns", [])
        rows = amort.get("data", [])
        payload = {"columns": columns, "data": rows}
        self._amortization_cache[secid] = payload
        return payload

    def has_amortization(self, secid: str, maturity_date=None) -> bool:
        payload = self.get_amortizations(secid)
        columns = payload.get("columns", [])
        rows = payload.get("data", [])
        if not rows:
            return False
        col_index = {name: i for i, name in enumerate(columns)}
        idx_date = col_index.get("amortdate")
        idx_valueprc = col_index.get("valueprc")
        idx_value = col_index.get("value")

        from datetime import datetime as _dt

        for row in rows:
            valueprc = row[idx_valueprc] if idx_valueprc is not None else None
            value = row[idx_value] if idx_value is not None else None
            amort_date = None
            if idx_date is not None and row[idx_date]:
                try:
                    amort_date = _dt.strptime(row[idx_date], "%Y-%m-%d").date()
                except ValueError:
                    amort_date = None

            if valueprc is not None and valueprc < 100:
                return True
            if value is not None and value > 0 and amort_date and maturity_date and amort_date < maturity_date:
                return True

        if maturity_date is None:
            return len(rows) > 1
        return False
