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

Запуск веб API:

```bash
uvicorn src.web.app:app --host 0.0.0.0 --port 8000 --reload
```

Веб-интерфейс: `http://127.0.0.1:8000/`  
Swagger API: `http://127.0.0.1:8000/docs`

Проверка:

```bash
curl "http://127.0.0.1:8000/health"
curl "http://127.0.0.1:8000/api/futures/search?q=gold"
curl "http://127.0.0.1:8000/api/futures/candles?ticker=RIH6"
curl "http://127.0.0.1:8000/api/bonds/search?currency=RUB&limit=3"
```

## Dev стенд (локально)

Создать отдельное dev‑окружение:

```bash
cp .env.dev.example .env.dev
```

Заполнить `.env.dev` токеном отдельного dev-бота.

Запуск локального стенда:

```bash
make dev-up
```

После запуска доступны:
- бот в контейнере `moex-bot-dev`
- веб-интерфейс `http://127.0.0.1:8000/`

Если запускаете вручную, задавайте ASCII project name:

```bash
COMPOSE_PROJECT_NAME=moexbotdev docker compose -f docker-compose.dev.yml --env-file .env.dev build bot
COMPOSE_PROJECT_NAME=moexbotdev docker compose -f docker-compose.dev.yml --env-file .env.dev build web
COMPOSE_PROJECT_NAME=moexbotdev docker compose -f docker-compose.dev.yml --env-file .env.dev up -d
```

Логи:

```bash
make dev-logs
make dev-logs-web
```

Остановка:

```bash
make dev-down
```

Пересборка:

```bash
make dev-restart
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
