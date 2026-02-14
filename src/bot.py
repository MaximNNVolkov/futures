from __future__ import annotations

import os
import asyncio
import tempfile
import logging
from datetime import datetime
from dataclasses import dataclass
from typing import List

from openpyxl import Workbook
import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib import dates as mdates
from matplotlib.patches import Rectangle
from dotenv import load_dotenv
from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, TimedOut
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from moex_lib.services.bond_bot_service import find_bonds_for_telegram
from moex_lib.filters.filter_types import BondType, CouponType
from src.config import settings
from src.moex.client import MoexClient
from src.moex.futures import FuturesCandlesGateway
from src.services.candles import CandlesService

logger = logging.getLogger(__name__)

TELEGRAM_CONNECT_TIMEOUT = 20
TELEGRAM_READ_TIMEOUT = 60
TELEGRAM_WRITE_TIMEOUT = 60
TELEGRAM_POOL_TIMEOUT = 20
MAX_MESSAGE_LEN = 4096
BONDS_FILTERS_KEY = "bonds_filters"

BONDS_DEFAULT_FILTERS = {
    "years_from": 0,
    "months_from": 0,
    "years_to": 50,
    "months_to": 0,
    "coupon_type": None,
    "bond_type": None,
    "has_amortization": None,
    "has_offer": None,
    "currency": "RUB",
    "limit": 3,
}

COUPON_TYPE_CYCLE = [None, "fixed", "float", "none"]
BOND_TYPE_CYCLE = [None, "ofz", "corporate", "municipal"]
TRISTATE_CYCLE = [None, True, False]
CURRENCY_CYCLE = [None, "RUB", "USD", "EUR", "CNY"]
LIMIT_CYCLE = [3, 5, 10, 20, 50]
MATURITY_FROM_YEARS_CYCLE = [0, 1, 3]
MATURITY_TO_YEARS_CYCLE = [3, 5, 10, 50]


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


def build_daily_chart(ticker: str, daily_rows: List[dict]) -> str:
    def _to_float(value) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    candles: List[tuple[float, float, float, float, float]] = []
    for row in daily_rows:
        begin = row.get("begin") or ""
        if not begin:
            continue
        try:
            date_part = begin.split()[0]
            candle_date = datetime.fromisoformat(date_part)
        except ValueError:
            continue
        open_price = _to_float(row.get("open"))
        high_price = _to_float(row.get("high"))
        low_price = _to_float(row.get("low"))
        close_price = _to_float(row.get("close"))
        if None in (open_price, high_price, low_price, close_price):
            continue
        candles.append(
            (
                mdates.date2num(candle_date),
                open_price,
                high_price,
                low_price,
                close_price,
            )
        )

    fd, path = tempfile.mkstemp(prefix=f"{ticker}_", suffix=".png")
    os.close(fd)

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.set_title(f"{ticker} Daily Candles (3y)")
    ax.set_xlabel("Date")
    ax.set_ylabel("Price")
    ax.grid(True, alpha=0.25)

    if candles:
        candle_width = 0.6
        for x, open_price, high_price, low_price, close_price in candles:
            color = "#2ca02c" if close_price >= open_price else "#d62728"
            ax.vlines(x, low_price, high_price, color=color, linewidth=1.0)
            body_low = min(open_price, close_price)
            body_height = abs(close_price - open_price)
            if body_height == 0:
                ax.hlines(open_price, x - candle_width / 2, x + candle_width / 2, color=color, linewidth=1.5)
            else:
                body = Rectangle(
                    (x - candle_width / 2, body_low),
                    candle_width,
                    body_height,
                    facecolor=color,
                    edgecolor=color,
                    linewidth=1.0,
                )
                ax.add_patch(body)

        locator = mdates.AutoDateLocator(minticks=6, maxticks=12)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))

        x_values = [item[0] for item in candles]
        lows = [item[3] for item in candles]
        highs = [item[2] for item in candles]
        ax.set_xlim(min(x_values) - 2, max(x_values) + 2)
        span = max(highs) - min(lows)
        pad = span * 0.05 if span > 0 else max(highs) * 0.01 or 1.0
        ax.set_ylim(min(lows) - pad, max(highs) + pad)
    else:
        ax.text(0.5, 0.5, "Нет данных для свечного графика", ha="center", va="center", transform=ax.transAxes)

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["awaiting_futures_ticker"] = False
    msg = (
        "Бот перезапущен.\n\n"
        "Доступные команды:\n"
        "/futures - получить график и Excel по фьючерсу\n"
        "/bonds - таблица облигаций"
    )
    await update.message.reply_text(msg)


async def _send_long_text(update: Update, text: str) -> None:
    if not update.message:
        return
    for i in range(0, len(text), MAX_MESSAGE_LEN):
        await update.message.reply_text(text[i : i + MAX_MESSAGE_LEN])


def _get_bonds_filters(context: ContextTypes.DEFAULT_TYPE) -> dict:
    filters_data = context.user_data.get(BONDS_FILTERS_KEY)
    if filters_data is None:
        filters_data = dict(BONDS_DEFAULT_FILTERS)
        context.user_data[BONDS_FILTERS_KEY] = filters_data
    return filters_data


def _cycle_value(current, options: list):
    try:
        idx = options.index(current)
    except ValueError:
        return options[0]
    return options[(idx + 1) % len(options)]


def _fmt_bond_filter_value(value) -> str:
    if value is None:
        return "любой"
    if value is True:
        return "да"
    if value is False:
        return "нет"
    return str(value)


def _bonds_menu_text(filters_data: dict) -> str:
    return (
        "Настройка фильтров облигаций:\n\n"
        f"Срок: от {filters_data['years_from']}г до {filters_data['years_to']}г\n"
        f"Тип купона: {_fmt_bond_filter_value(filters_data['coupon_type'])}\n"
        f"Тип облигации: {_fmt_bond_filter_value(filters_data['bond_type'])}\n"
        f"Амортизация: {_fmt_bond_filter_value(filters_data['has_amortization'])}\n"
        f"Оферта: {_fmt_bond_filter_value(filters_data['has_offer'])}\n"
        f"Валюта: {_fmt_bond_filter_value(filters_data['currency'])}\n"
        f"Лимит: {filters_data['limit']}\n\n"
        "Нажмите на параметры для изменения, затем «Показать таблицу»."
    )


def _bonds_menu_keyboard(filters_data: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text=f"Срок от: {filters_data['years_from']}г",
                    callback_data="bonds:cycle:years_from",
                ),
                InlineKeyboardButton(
                    text=f"Срок до: {filters_data['years_to']}г",
                    callback_data="bonds:cycle:years_to",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"Купон: {_fmt_bond_filter_value(filters_data['coupon_type'])}",
                    callback_data="bonds:cycle:coupon_type",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Тип: {_fmt_bond_filter_value(filters_data['bond_type'])}",
                    callback_data="bonds:cycle:bond_type",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Аморт.: {_fmt_bond_filter_value(filters_data['has_amortization'])}",
                    callback_data="bonds:cycle:has_amortization",
                ),
                InlineKeyboardButton(
                    text=f"Оферта: {_fmt_bond_filter_value(filters_data['has_offer'])}",
                    callback_data="bonds:cycle:has_offer",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"Валюта: {_fmt_bond_filter_value(filters_data['currency'])}",
                    callback_data="bonds:cycle:currency",
                ),
                InlineKeyboardButton(
                    text=f"Лимит: {filters_data['limit']}",
                    callback_data="bonds:cycle:limit",
                ),
            ],
            [
                InlineKeyboardButton(text="Показать таблицу", callback_data="bonds:run"),
                InlineKeyboardButton(text="Сброс", callback_data="bonds:reset"),
            ],
        ]
    )


def _build_bonds_kwargs(filters_data: dict) -> dict:
    coupon_type = filters_data["coupon_type"]
    bond_type = filters_data["bond_type"]
    return {
        "years_from": filters_data["years_from"],
        "months_from": filters_data["months_from"],
        "years_to": filters_data["years_to"],
        "months_to": filters_data["months_to"],
        "coupon_type": CouponType(coupon_type) if coupon_type else None,
        "bond_type": BondType(bond_type) if bond_type else None,
        "has_amortization": filters_data["has_amortization"],
        "has_offer": filters_data["has_offer"],
        "currency": filters_data["currency"],
        "limit": filters_data["limit"],
    }


async def _send_futures_payload(update: Update, ticker: str) -> None:
    if not update.message:
        return

    service = build_service()
    await update.message.reply_text(f"Получаю свечи для {ticker}...")

    hourly_rows = await asyncio.to_thread(service.get_hourly_1y, ticker)
    daily_rows = await asyncio.to_thread(service.get_daily_3y, ticker)

    file_path = await asyncio.to_thread(build_excel, ticker, hourly_rows, daily_rows)
    chart_path = await asyncio.to_thread(build_daily_chart, ticker, daily_rows)
    try:
        try:
            with open(chart_path, "rb") as img:
                await update.message.reply_photo(
                    photo=img,
                    caption=f"{ticker}: daily candles (3y)",
                    connect_timeout=TELEGRAM_CONNECT_TIMEOUT,
                    read_timeout=TELEGRAM_READ_TIMEOUT,
                    write_timeout=TELEGRAM_WRITE_TIMEOUT,
                    pool_timeout=TELEGRAM_POOL_TIMEOUT,
                )
        except TimedOut:
            logger.warning("Timed out while sending chart for %s, retrying once", ticker)
            with open(chart_path, "rb") as img:
                await update.message.reply_photo(
                    photo=img,
                    caption=f"{ticker}: daily candles (3y)",
                    connect_timeout=TELEGRAM_CONNECT_TIMEOUT,
                    read_timeout=TELEGRAM_READ_TIMEOUT,
                    write_timeout=TELEGRAM_WRITE_TIMEOUT,
                    pool_timeout=TELEGRAM_POOL_TIMEOUT,
                )
        try:
            with open(file_path, "rb") as f:
                await update.message.reply_document(
                    document=f,
                    filename=f"{ticker}_candles.xlsx",
                    caption=f"{ticker}: hourly_1y и daily_3y",
                    connect_timeout=TELEGRAM_CONNECT_TIMEOUT,
                    read_timeout=TELEGRAM_READ_TIMEOUT,
                    write_timeout=TELEGRAM_WRITE_TIMEOUT,
                    pool_timeout=TELEGRAM_POOL_TIMEOUT,
                )
        except TimedOut:
            logger.warning("Timed out while sending document for %s, retrying once", ticker)
            with open(file_path, "rb") as f:
                await update.message.reply_document(
                    document=f,
                    filename=f"{ticker}_candles.xlsx",
                    caption=f"{ticker}: hourly_1y и daily_3y",
                    connect_timeout=TELEGRAM_CONNECT_TIMEOUT,
                    read_timeout=TELEGRAM_READ_TIMEOUT,
                    write_timeout=TELEGRAM_WRITE_TIMEOUT,
                    pool_timeout=TELEGRAM_POOL_TIMEOUT,
                )
    except TimedOut:
        await update.message.reply_text(
            "Telegram не ответил вовремя при отправке файла. Попробуйте еще раз через минуту."
        )
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
        if os.path.exists(chart_path):
            os.remove(chart_path)


async def futures(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    if context.args:
        context.user_data["awaiting_futures_ticker"] = False
        ticker = context.args[-1].upper()
        await _send_futures_payload(update, ticker)
        return

    context.user_data["awaiting_futures_ticker"] = True
    await update.message.reply_text("Введите тикер фьючерса, например: RIH6")


async def bonds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    filters_data = _get_bonds_filters(context)
    await update.message.reply_text(
        _bonds_menu_text(filters_data),
        reply_markup=_bonds_menu_keyboard(filters_data),
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    text = (update.message.text or "").strip()
    if not text:
        return
    if context.user_data.get("awaiting_futures_ticker"):
        context.user_data["awaiting_futures_ticker"] = False
        ticker = text.split()[-1].upper()
        await _send_futures_payload(update, ticker)
        return

    await update.message.reply_text("Используйте /futures для запроса по фьючерсу или /bonds для облигаций.")


async def bonds_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    if not (query.data or "").startswith("bonds:"):
        return

    try:
        await query.answer()
        data = query.data or ""
        filters_data = _get_bonds_filters(context)

        if data == "bonds:reset":
            filters_data.clear()
            filters_data.update(BONDS_DEFAULT_FILTERS)
        elif data == "bonds:run":
            if query.message:
                await query.message.reply_text("Подбираю облигации...")
                kwargs = _build_bonds_kwargs(filters_data)
                table = await asyncio.to_thread(find_bonds_for_telegram, **kwargs)
                for i in range(0, len(table), MAX_MESSAGE_LEN):
                    await query.message.reply_text(table[i : i + MAX_MESSAGE_LEN])
            return
        elif data.startswith("bonds:cycle:"):
            field = data.split(":")[-1]
            if field == "coupon_type":
                filters_data[field] = _cycle_value(filters_data[field], COUPON_TYPE_CYCLE)
            elif field == "bond_type":
                filters_data[field] = _cycle_value(filters_data[field], BOND_TYPE_CYCLE)
            elif field in {"has_amortization", "has_offer"}:
                filters_data[field] = _cycle_value(filters_data[field], TRISTATE_CYCLE)
            elif field == "currency":
                filters_data[field] = _cycle_value(filters_data[field], CURRENCY_CYCLE)
            elif field == "limit":
                filters_data[field] = _cycle_value(filters_data[field], LIMIT_CYCLE)
            elif field == "years_from":
                filters_data[field] = _cycle_value(filters_data[field], MATURITY_FROM_YEARS_CYCLE)
                if filters_data["years_from"] > filters_data["years_to"]:
                    filters_data["years_to"] = filters_data["years_from"]
            elif field == "years_to":
                filters_data[field] = _cycle_value(filters_data[field], MATURITY_TO_YEARS_CYCLE)
                if filters_data["years_to"] < filters_data["years_from"]:
                    filters_data["years_from"] = filters_data["years_to"]

        try:
            await query.edit_message_text(
                _bonds_menu_text(filters_data),
                reply_markup=_bonds_menu_keyboard(filters_data),
            )
        except BadRequest as exc:
            if "Message is not modified" not in str(exc):
                raise
    except Exception:
        logger.exception("Failed to process bonds callback")
        if query.message:
            await query.message.reply_text(
                "Не удалось обработать нажатие кнопки. Попробуйте еще раз /bonds."
            )


async def post_init(application) -> None:
    await application.bot.set_my_commands(
        [
            BotCommand("start", "перезапуск бота"),
            BotCommand("futures", "график и excel по фьючерсу"),
            BotCommand("bonds", "фильтры и таблица облигаций"),
        ]
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled bot error", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "Внутренняя ошибка при обработке запроса. Попробуйте повторить команду."
            )
        except Exception:
            logger.exception("Failed to send error message to user")


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=logging.INFO,
    )
    # Suppress noisy HTTP client logs that include Bot API URLs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN env var")

    app = (
        ApplicationBuilder()
        .token(token)
        .connect_timeout(TELEGRAM_CONNECT_TIMEOUT)
        .read_timeout(TELEGRAM_READ_TIMEOUT)
        .write_timeout(TELEGRAM_WRITE_TIMEOUT)
        .pool_timeout(TELEGRAM_POOL_TIMEOUT)
        .post_init(post_init)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("futures", futures))
    app.add_handler(CommandHandler("bonds", bonds))
    app.add_handler(CallbackQueryHandler(bonds_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(error_handler)
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
