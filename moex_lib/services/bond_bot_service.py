from __future__ import annotations

from ..api.bonds_api import BondsApi
from ..filters.bond_filters import BondSearchFilters
from ..filters.filter_types import BondType, CouponType
from ..filters.maturity_delta import MaturityDelta
from ..utils.helpers import format_bonds_table, select_top_bonds_by_coupon_yield
from .bond_search_service import BondSearchService


def find_bonds_for_telegram(
    *,
    years_from: int = 0,
    months_from: int = 0,
    years_to: int = 50,
    months_to: int = 0,
    coupon_type: CouponType | None = None,
    bond_type: BondType | None = None,
    has_amortization: bool | None = None,
    has_offer: bool | None = None,
    currency: str | None = "RUB",
    limit: int = 3,
) -> str:
    """Build text response for Telegram with selected bonds."""
    filters = BondSearchFilters(
        maturity_from=MaturityDelta(years=years_from, months=months_from),
        maturity_to=MaturityDelta(years=years_to, months=months_to),
        coupon_type=coupon_type,
        bond_type=bond_type,
        currency=currency,
        has_amortization=has_amortization,
        has_offer=has_offer,
    )

    service = BondSearchService(BondsApi())
    bonds = service.search(filters)

    if not bonds:
        return "По заданным фильтрам облигации не найдены."

    top = select_top_bonds_by_coupon_yield(bonds, limit)
    service.enrich_amortization(top)

    header = f"Найдено облигаций: {len(bonds)}\nПоказано: {len(top)}\n\n"
    return header + format_bonds_table(top)
