DEV_PROJECT_NAME = moexbotdev
DEV_COMPOSE = COMPOSE_PROJECT_NAME=$(DEV_PROJECT_NAME) docker compose -f docker-compose.dev.yml --env-file .env.dev
DEV_BUILD_SEQ = $(DEV_COMPOSE) build bot && $(DEV_COMPOSE) build web

.PHONY: dev-up dev-down dev-logs dev-logs-web dev-build dev-restart web-dev

dev-up:
	$(DEV_BUILD_SEQ)
	$(DEV_COMPOSE) up -d

dev-down:
	$(DEV_COMPOSE) down

dev-logs:
	$(DEV_COMPOSE) logs -f bot

dev-logs-web:
	$(DEV_COMPOSE) logs -f web

dev-build:
	$(DEV_COMPOSE) build --no-cache

dev-restart:
	$(DEV_COMPOSE) down
	$(DEV_BUILD_SEQ)
	$(DEV_COMPOSE) up -d

web-dev:
	uvicorn src.web.app:app --host 0.0.0.0 --port 8000 --reload
