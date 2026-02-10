from __future__ import annotations

import argparse

from src.config import settings
from src.moex.client import MoexClient
from src.moex.futures import FuturesCandlesGateway
from src.services.candles import CandlesService
from src.storage.sqlite import SQLiteStorage


def build_service(use_storage: bool) -> CandlesService:
    client = MoexClient(base_url=settings.moex_base_url)
    gateway = FuturesCandlesGateway(client=client)
    storage = SQLiteStorage(db_path=settings.db_path) if use_storage else None
    return CandlesService(gateway=gateway, storage=storage)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch MOEX futures candles.")
    parser.add_argument("--ticker", required=True, help="MOEX futures ticker, e.g. RIH6")
    parser.add_argument("--hourly", action="store_true", help="Fetch hourly candles for 1 year")
    parser.add_argument("--daily", action="store_true", help="Fetch daily candles for 3 years")
    parser.add_argument("--no-db", action="store_true", help="Do not persist to SQLite")
    args = parser.parse_args()

    if not args.hourly and not args.daily:
        parser.error("Specify at least one of --hourly or --daily")

    service = build_service(use_storage=not args.no_db)

    if args.hourly:
        rows = service.get_hourly_1y(args.ticker)
        print(f"Hourly 1y candles: {len(rows)} rows")

    if args.daily:
        rows = service.get_daily_3y(args.ticker)
        print(f"Daily 3y candles: {len(rows)} rows")

    if not args.no_db:
        print(f"Saved to SQLite: {settings.db_path}")


if __name__ == "__main__":
    main()

