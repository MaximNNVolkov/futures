DEV_PROJECT_NAME = moexbotdev
DEV_COMPOSE = COMPOSE_PROJECT_NAME=$(DEV_PROJECT_NAME) docker compose -f docker-compose.dev.yml --env-file .env.dev

.PHONY: dev-up dev-down dev-logs dev-build dev-restart

dev-up:
	$(DEV_COMPOSE) up -d --build

dev-down:
	$(DEV_COMPOSE) down

dev-logs:
	$(DEV_COMPOSE) logs -f bot

dev-build:
	$(DEV_COMPOSE) build --no-cache

dev-restart:
	$(DEV_COMPOSE) down
	$(DEV_COMPOSE) up -d --build
