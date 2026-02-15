from __future__ import annotations

from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from moex_lib.api.bonds_api import BondsApi
from moex_lib.filters.bond_filters import BondSearchFilters
from moex_lib.filters.filter_types import BondType, CouponType
from moex_lib.filters.maturity_delta import MaturityDelta
from moex_lib.models.bond import Bond
from moex_lib.services.bond_search_service import BondSearchService
from src.config import settings
from src.moex.client import MoexClient
from src.moex.futures import FuturesCandlesGateway
from src.services.candles import CandlesService

MAX_FUTURES_SEARCH_RESULTS = 50
FUTURES_CONTRACTNAME_CACHE: dict[str, str] = {}
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="MOEX Bot API",
    version="0.1.0",
    description="HTTP API for futures candles and bonds search",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _build_candles_service() -> CandlesService:
    client = MoexClient(base_url=settings.moex_base_url)
    gateway = FuturesCandlesGateway(client=client)
    return CandlesService(gateway=gateway, storage=None)


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return value.lower().replace("ё", "е").strip()


def _get_contractname_by_secid(client: MoexClient, secid: str) -> str:
    cached = FUTURES_CONTRACTNAME_CACHE.get(secid)
    if cached is not None:
        return cached

    payload = client.get_json(
        path=f"securities/{secid}.json",
        params={"iss.meta": "off", "iss.only": "description"},
    )
    description = payload.get("description", {}) or {}
    columns = description.get("columns", [])
    rows = description.get("data", [])
    if not columns or not rows:
        FUTURES_CONTRACTNAME_CACHE[secid] = ""
        return ""

    idx = {name: i for i, name in enumerate(columns)}
    idx_name = idx.get("name")
    idx_value = idx.get("value")
    if idx_name is None or idx_value is None:
        FUTURES_CONTRACTNAME_CACHE[secid] = ""
        return ""

    contract_name = ""
    fallback_name = ""
    for row in rows:
        name = str(row[idx_name] or "").strip().upper()
        value = str(row[idx_value] or "").strip()
        if not value:
            continue
        if name == "CONTRACTNAME":
            contract_name = value
            break
        if not fallback_name and name in {"NAME", "SHORTNAME"}:
            fallback_name = value

    result = contract_name or fallback_name
    FUTURES_CONTRACTNAME_CACHE[secid] = result
    return result


def _search_futures_by_phrase(phrase: str, limit: int) -> list[dict[str, str]]:
    query = _normalize_text(phrase)
    if not query:
        return []

    client = MoexClient(base_url=settings.moex_base_url)
    rows = client.get_table_paged(
        path="engines/futures/markets/forts/securities.json",
        params={"iss.meta": "off", "iss.only": "securities"},
        table="securities",
        page_size=1000,
    )

    matched: list[dict[str, str]] = []
    for row in rows:
        board_id = str(row.get("BOARDID") or "")
        if board_id and board_id.upper() != "RFUD":
            continue

        secid = str(row.get("SECID") or "").strip()
        if not secid:
            continue

        shortname = str(row.get("SHORTNAME") or "").strip()
        contract_name = _get_contractname_by_secid(client, secid)
        if query in _normalize_text(contract_name):
            matched.append(
                {
                    "secid": secid,
                    "shortname": shortname,
                    "contract_name": contract_name,
                }
            )
        if len(matched) >= limit:
            break
    return matched


def _serialize_bond(bond: Bond) -> dict[str, Any]:
    payload = asdict(bond)
    if bond.maturity_date:
        payload["maturity_date"] = bond.maturity_date.isoformat()
    payload["bond_type"] = (
        "ofz"
        if bond.is_ofz
        else "municipal"
        if bond.is_municipal
        else "corporate"
        if bond.is_corporate
        else "unknown"
    )
    return payload


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/futures/search")
async def search_futures(
    q: str = Query(..., min_length=1, description="Part of contract name"),
    limit: int = Query(12, ge=1, le=MAX_FUTURES_SEARCH_RESULTS),
) -> dict[str, Any]:
    results = await run_in_threadpool(_search_futures_by_phrase, q, limit)
    return {"query": q, "count": len(results), "results": results}


@app.get("/api/futures/candles")
async def futures_candles(
    ticker: str = Query(..., min_length=1, max_length=32, description="Futures ticker, e.g. RIH6"),
) -> dict[str, Any]:
    service = _build_candles_service()
    ticker_upper = ticker.strip().upper()
    hourly = await run_in_threadpool(service.get_hourly_1y, ticker_upper)
    daily = await run_in_threadpool(service.get_daily_3y, ticker_upper)

    if not hourly and not daily:
        raise HTTPException(
            status_code=404,
            detail="Такой тикер не существует.",
        )

    return {
        "ticker": ticker_upper,
        "hourly_count": len(hourly),
        "daily_count": len(daily),
        "hourly": hourly,
        "daily": daily,
    }


@app.get("/api/bonds/search")
async def search_bonds(
    years_from: int = Query(0, ge=0, le=50),
    months_from: int = Query(0, ge=0, le=11),
    years_to: int = Query(50, ge=0, le=50),
    months_to: int = Query(0, ge=0, le=11),
    coupon_type: Literal["fixed", "float", "none"] | None = None,
    bond_type: Literal["ofz", "corporate", "municipal"] | None = None,
    coupon_frequency: int | None = Query(None, ge=0, le=12),
    currency: str | None = Query(None, min_length=1, max_length=10),
    has_amortization: bool | None = None,
    has_offer: bool | None = None,
    limit: int = Query(3, ge=1, le=100),
) -> dict[str, Any]:
    maturity_from = MaturityDelta(years=years_from, months=months_from)
    maturity_to = MaturityDelta(years=years_to, months=months_to)
    if maturity_from.to_months() > maturity_to.to_months():
        raise HTTPException(status_code=400, detail="maturity_from must be <= maturity_to")

    filters = BondSearchFilters(
        maturity_from=maturity_from,
        maturity_to=maturity_to,
        coupon_type=CouponType(coupon_type) if coupon_type else None,
        bond_type=BondType(bond_type) if bond_type else None,
        coupon_frequency=coupon_frequency,
        currency=currency,
        has_amortization=has_amortization,
        has_offer=has_offer,
    )
    service = BondSearchService(BondsApi())
    bonds = await run_in_threadpool(service.search, filters)
    bonds.sort(key=lambda b: b.maturity_date or date.max)
    bonds = bonds[:limit]

    return {
        "count": len(bonds),
        "results": [_serialize_bond(bond) for bond in bonds],
    }
