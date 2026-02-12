from __future__ import annotations

from datetime import date
from typing import Iterable

from ..models.bond import Bond


def to_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", "."))
        except ValueError:
            return None
    return None


def coupons_per_year(bond: Bond) -> float | None:
    if bond.coupon_period and bond.coupon_period > 0:
        return 365 / bond.coupon_period
    if bond.coupon_frequency and bond.coupon_frequency > 0:
        return float(bond.coupon_frequency)
    return None


def price_money(bond: Bond) -> float | None:
    current_price = to_float(bond.current_price)
    face_value = to_float(bond.face_value)
    if current_price is None or face_value is None:
        return None
    return face_value * current_price / 100


def annual_coupon_amount(bond: Bond) -> float | None:
    next_coupon = to_float(bond.next_coupon)
    if next_coupon is None:
        return None
    per_year = coupons_per_year(bond)
    if per_year is None:
        return None
    return next_coupon * per_year


def coupon_yield_pct(bond: Bond) -> float | None:
    price = price_money(bond)
    annual_coupon = annual_coupon_amount(bond)
    if price is None or annual_coupon is None or price <= 0:
        return None
    return annual_coupon / price * 100


def total_yield_pct(bond: Bond) -> float | None:
    price = price_money(bond)
    annual_coupon = annual_coupon_amount(bond)
    if price is None or annual_coupon is None or price <= 0:
        return None
    if bond.maturity_date is None:
        return None
    days_to_maturity = (bond.maturity_date - date.today()).days
    if days_to_maturity <= 0:
        return None
    years_to_maturity = days_to_maturity / 365
    if years_to_maturity <= 0:
        return None
    face_value = to_float(bond.face_value)
    if face_value is None:
        return None
    redemption_gain_per_year = (face_value - price) / years_to_maturity
    return (annual_coupon + redemption_gain_per_year) / price * 100


def sort_bonds_by_coupon_yield(bonds: Iterable[Bond]) -> list[Bond]:
    bonds_list = list(bonds)
    bonds_list.sort(
        key=lambda b: (
            coupon_yield_pct(b) is None,
            -(coupon_yield_pct(b) or 0),
        )
    )
    return bonds_list


def select_top_bonds_by_coupon_yield(bonds: Iterable[Bond], limit: int | None = None) -> list[Bond]:
    bonds_list = sort_bonds_by_coupon_yield(bonds)
    if limit is not None:
        return bonds_list[:limit]
    return bonds_list


def format_bonds_table(bonds: Iterable[Bond], limit: int | None = None) -> str:
    def fmt_num(value) -> str:
        if value is None:
            return "н/д"
        if isinstance(value, (int, float)):
            return f"{value:.2f}".replace(".", ",")
        return str(value)

    bonds_list = select_top_bonds_by_coupon_yield(bonds, limit)

    def fmt_coupon_type(value: str) -> str:
        mapping = {
            "fixed": "фиксированный",
            "float": "плавающий",
            "none": "без купона",
            "unknown": "неизвестно",
        }
        if not value:
            return "н/д"
        return mapping.get(value, "неизвестно")

    def fmt_bool(value: bool) -> str:
        return "Да" if value else "Нет"

    def fmt_currency(code: str | None) -> str:
        if not code:
            return "н/д"
        mapping = {
            "RUB": "руб",
            "RUR": "руб",
            "SUR": "руб",
            "USD": "долл. США",
            "EUR": "евро",
            "CNY": "юань",
            "GBP": "фунт стерл.",
            "CHF": "швейц. франк",
            "JPY": "иена",
        }
        return mapping.get(code, f"валюта {code}")

    rows = []
    header = [
        "Код",
        "Название",
        "Погашение",
        "До погаш.",
        "Тип купона",
        "Период купона, дн",
        "Валюта",
        "Цена, %",
        "След. купон",
        "Купон. доходн., %",
        "Полн. доходн., %",
        "Аморт.",
        "Оферта",
    ]
    rows.append(header)

    for b in bonds_list:
        maturity_left = "н/д"
        if b.maturity_date:
            days_left = (b.maturity_date - date.today()).days
            if days_left > 0:
                total_months = max(0, days_left // 30)
                years = total_months // 12
                months = total_months % 12
                maturity_left = f"{years}г {months}м"
            else:
                maturity_left = "погашена"
        rows.append(
            [
                b.secid,
                b.name or "н/д",
                b.maturity_date.isoformat() if b.maturity_date else "-",
                maturity_left,
                fmt_coupon_type(b.coupon_type),
                str(b.coupon_period) if b.coupon_period is not None else "н/д",
                fmt_currency(b.currency),
                fmt_num(b.current_price),
                fmt_num(b.next_coupon),
                fmt_num(coupon_yield_pct(b)),
                fmt_num(total_yield_pct(b)),
                fmt_bool(b.has_amortization),
                fmt_bool(b.has_offer),
            ]
        )

    widths = [max(len(str(row[i])) for row in rows) for i in range(len(header))]

    lines = []
    for idx, row in enumerate(rows):
        line = "  ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row))
        lines.append(line)
        if idx == 0:
            lines.append("  ".join("-" * widths[i] for i in range(len(header))))

    return "\n".join(lines)
