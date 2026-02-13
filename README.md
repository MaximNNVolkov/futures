# MOEX Futures Candles

Проект получает свечные данные по фьючерсам с MOEX ISS и сохраняет их в SQLite.

Два ключевых метода:
- часовые свечи за 1 год
- дневные свечи за последние 3 года

## Быстрый старт

Установить зависимости:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Пример запуска:

```bash
python -m src.cli --ticker RIH6 --hourly
python -m src.cli --ticker RIH6 --daily
```

Запуск телеграм-бота:

```bash
echo "TELEGRAM_BOT_TOKEN=YOUR_TOKEN" > .env
python -m src.bot
```

## Деплой на сервер (Docker)

На сервере (Ubuntu/VPS) в папке проекта:

```bash
cp .env.example .env
```

Заполнить `.env` (минимум `TELEGRAM_BOT_TOKEN`), затем запустить:

```bash
docker compose up -d --build
```

Проверка логов:

```bash
docker compose logs -f bot
```

Обновление после изменений:

```bash
git pull
docker compose up -d --build
```

## Структура

- `src/moex/` — клиент MOEX ISS и доменная логика по фьючерсам
- `src/services/` — бизнес‑сервисы (получение свечей)
- `src/storage/` — слой хранения (SQLite)
- `src/cli.py` — CLI для запуска
