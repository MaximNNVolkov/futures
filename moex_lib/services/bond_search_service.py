from __future__ import annotations

from typing import List
from datetime import date, datetime

from ..filters.bond_filters import BondSearchFilters
from ..models.bond import Bond
from ..utils.maturity import months_to_maturity

class BondSearchService:

    def __init__(self, api):
        self.api = api

    def enrich_amortization(self, bonds: list[Bond]) -> None:
        if not hasattr(self.api, "has_amortization"):
            return
        for bond in bonds:
            try:
                bond.has_amortization = self.api.has_amortization(
                    bond.secid,
                    maturity_date=bond.maturity_date,
                )
            except Exception:
                continue

    def search(self, filters: BondSearchFilters) -> List[Bond]:
        raw_data = self.api.get_bonds()
        bonds = self._parse_bonds(raw_data)

        today = date.today()

        if filters.maturity_from or filters.maturity_to:
            bonds_filtered = []

            for b in bonds:
                if not b.maturity_date:
                    continue

                months = months_to_maturity(today, b.maturity_date)

                # погашенные сразу отбрасываем
                if months < 0:
                    continue

                if filters.maturity_from:
                    if months < filters.maturity_from.to_months():
                        continue

                if filters.maturity_to:
                    if months > filters.maturity_to.to_months():
                        continue

                bonds_filtered.append(b)

            bonds = bonds_filtered

        #if filters.maturity_to:
        #    bonds = [b for b in bonds if b.maturity_date and b.maturity_date <= filters.maturity_to]

        if filters.currency:
            target_currency = self._normalize_currency(filters.currency)
            bonds = [b for b in bonds if self._normalize_currency(b.currency) == target_currency]

        if filters.coupon_frequency:
            bonds = [b for b in bonds if b.coupon_frequency == filters.coupon_frequency]

        if filters.coupon_type:
            bonds = [b for b in bonds if b.coupon_type == filters.coupon_type.value]

        if filters.bond_type:
            bonds = self._filter_by_bond_type(bonds, filters.bond_type)

        if filters.has_amortization is not None:
            self.enrich_amortization(bonds)

        if filters.has_amortization is not None:
            bonds = [b for b in bonds if b.has_amortization == filters.has_amortization]

        if filters.has_offer is not None:
            bonds = [b for b in bonds if b.has_offer == filters.has_offer]

        return bonds

    @staticmethod
    def _normalize_currency(currency: str | None) -> str | None:
        if currency is None:
            return None
        upper = currency.upper()
        aliases = {
            "RUR": "RUB",
            "SUR": "RUB",
        }
        return aliases.get(upper, upper)

    def _filter_by_bond_type(self, bonds, bond_type):
        if bond_type.value == "ofz":
            return [b for b in bonds if b.is_ofz]
        if bond_type.value == "municipal":
            return [b for b in bonds if b.is_municipal]
        if bond_type.value == "corporate":
            return [b for b in bonds if b.is_corporate]
        return bonds

    def _parse_bonds(self, raw_data: dict):
        securities = raw_data.get("securities")
        if not securities:
            return []

        columns = securities.get("columns", [])
        data = securities.get("data", [])

        if not columns or not data:
            return []

        col_index = {name: i for i, name in enumerate(columns)}

        def get(row, col):
            idx = col_index.get(col)
            return row[idx] if idx is not None else None

        market = raw_data.get("marketdata") or {}
        market_columns = market.get("columns", [])
        market_data = market.get("data", [])
        market_col_index = {name: i for i, name in enumerate(market_columns)}

        def mget(row, col):
            idx = market_col_index.get(col)
            return row[idx] if idx is not None else None

        market_by_secid = {}
        if market_col_index and market_data:
            for row in market_data:
                secid = mget(row, "SECID")
                if secid:
                    market_by_secid[secid] = row

        def coupon_type_rank(value: str) -> int:
            ranking = {
                "float": 3,
                "fixed": 2,
                "none": 1,
                "unknown": 0,
            }
            return ranking.get(value, 0)

        bonds_by_secid = {}

        for row in data:
            secid = get(row, "SECID")
            if not secid:
                continue

            name = get(row, "SHORTNAME") or secid

            mat_raw = get(row, "MATDATE")
            if mat_raw:
                try:
                    maturity_date = datetime.strptime(mat_raw, "%Y-%m-%d").date()
                except ValueError:
                    maturity_date = None
            else:
                maturity_date = None

            sectype = (get(row, "SECTYPE") or "").strip().upper()
            is_ofz = secid.startswith("SU") or (sectype in {"3", "5"})
            is_municipal = sectype in {"4", "C"}
            is_corporate = sectype in {"6", "7", "8"}
            if not is_ofz and not is_municipal and not is_corporate:
                is_corporate = True

            market_row = market_by_secid.get(secid)
            current_price = None
            if market_row:
                for col in ("LAST", "MARKETPRICE", "WAPRICE"):
                    current_price = mget(market_row, col)
                    if current_price is not None:
                        break

            next_coupon = get(row, "COUPONVALUE")

            bond = Bond(
                secid=secid,
                name=name,
                maturity_date=maturity_date,
                coupon_type=self._detect_coupon_type(row, col_index),
                coupon_frequency=get(row, "COUPONFREQUENCY"),
                coupon_period=get(row, "COUPONPERIOD"),
                currency=get(row, "FACEUNIT") or "RUB",
                face_value=get(row, "FACEVALUE"),
                is_ofz=is_ofz,
                is_municipal=is_municipal,
                is_corporate=is_corporate,
                has_amortization=bool(get(row, "AMORTIZATION")),
                has_offer=bool(get(row, "OFFERDATE")),
                current_price=current_price,
                next_coupon=next_coupon,
            )

            existing = bonds_by_secid.get(secid)
            if existing is None:
                bonds_by_secid[secid] = bond
                continue

            if existing.maturity_date is None and bond.maturity_date is not None:
                existing.maturity_date = bond.maturity_date
            if existing.coupon_frequency is None and bond.coupon_frequency is not None:
                existing.coupon_frequency = bond.coupon_frequency
            if existing.coupon_period is None and bond.coupon_period is not None:
                existing.coupon_period = bond.coupon_period
            if coupon_type_rank(bond.coupon_type) > coupon_type_rank(existing.coupon_type):
                existing.coupon_type = bond.coupon_type
            if existing.face_value is None and bond.face_value is not None:
                existing.face_value = bond.face_value
            if existing.current_price is None and bond.current_price is not None:
                existing.current_price = bond.current_price
            if existing.next_coupon is None and bond.next_coupon is not None:
                existing.next_coupon = bond.next_coupon

            existing.has_amortization = existing.has_amortization or bond.has_amortization
            existing.has_offer = existing.has_offer or bond.has_offer
            existing.is_ofz = existing.is_ofz or bond.is_ofz
            existing.is_municipal = existing.is_municipal or bond.is_municipal
            corporate_seen = existing.is_corporate or bond.is_corporate
            existing.is_corporate = corporate_seen and (not existing.is_ofz) and (not existing.is_municipal)

        return list(bonds_by_secid.values())

    def _detect_coupon_type(self, row, col_index) -> str:
        """
        fixed / float / none
        """
        coupon_rate = row[col_index["COUPONPERCENT"]] if "COUPONPERCENT" in col_index else None

        coupon_type_parts = []
        for col in ("BONDTYPE", "COUPONTYPE"):
            idx = col_index.get(col)
            if idx is None:
                continue
            value = row[idx]
            if value:
                coupon_type_parts.append(str(value))
        coupon_type_text = " ".join(coupon_type_parts).lower()

        if coupon_type_text:
            none_markers = ("безкупон", "бескупон", "zero", "no coupon", "нул")
            float_markers = (
                "перем",
                "плав",
                "float",
                "variable",
                "индекс",
                "инфля",
                "ruonia",
                "mosprime",
                "ключ",
                "key rate",
                "link",
                "rate",
            )
            fixed_markers = ("фикс", "fixed", "пост", "constant")
            if any(m in coupon_type_text for m in none_markers):
                return "none"
            if any(m in coupon_type_text for m in float_markers):
                return "float"
            if any(m in coupon_type_text for m in fixed_markers):
                return "fixed"

        if coupon_rate in (None, 0):
            return "none"

        return "unknown"
