from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from typing import List

from openpyxl import Workbook
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from src.config import settings
from src.moex.client import MoexClient
from src.moex.futures import FuturesCandlesGateway
from src.services.candles import CandlesService


@dataclass
class BotConfig:
    token: str


def build_service() -> CandlesService:
    client = MoexClient(base_url=settings.moex_base_url)
    gateway = FuturesCandlesGateway(client=client)
    return CandlesService(gateway=gateway, storage=None)


def _split_dt(value: str) -> tuple[str, str]:
    if not value:
        return "", ""
    parts = value.split()
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def _write_sheet(ws, title: str, rows: List[dict]) -> None:
    ws.title = title
    ws.append(["Date", "Time", "Open", "High", "Low", "Close", "Volume"])
    for row in rows:
        date_part, time_part = _split_dt(row.get("begin") or "")
        ws.append(
            [
                date_part,
                time_part,
                row.get("open"),
                row.get("high"),
                row.get("low"),
                row.get("close"),
                row.get("volume"),
            ]
        )


def build_excel(ticker: str, hourly_rows: List[dict], daily_rows: List[dict]) -> str:
    wb = Workbook()
    ws_hourly = wb.active
    _write_sheet(ws_hourly, "hourly_1y", hourly_rows)
    ws_daily = wb.create_sheet("daily_3y")
    _write_sheet(ws_daily, "daily_3y", daily_rows)

    fd, path = tempfile.mkstemp(prefix=f"{ticker}_", suffix=".xlsx")
    os.close(fd)
    wb.save(path)
    return path


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = (
        "Привет! Отправь тикер фьючерса, например: RIH6\n"
        "Или используй команду: /ticker RIH6"
    )
    await update.message.reply_text(msg)


async def handle_ticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    text = (update.message.text or "").strip()
    if not text:
        return
    ticker = text.split()[-1].upper()

    service = build_service()
    await update.message.reply_text(f"Получаю свечи для {ticker}...")

    hourly_rows = service.get_hourly_1y(ticker)
    daily_rows = service.get_daily_3y(ticker)

    file_path = build_excel(ticker, hourly_rows, daily_rows)
    try:
        with open(file_path, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=f"{ticker}_candles.xlsx",
                caption=f"{ticker}: hourly_1y и daily_3y",
            )
    finally:
        os.remove(file_path)


def main() -> None:
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN env var")

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ticker", handle_ticker))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ticker))
    app.run_polling()


if __name__ == "__main__":
    main()
