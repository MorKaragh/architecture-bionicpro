COMPOSE = docker compose
export AIRFLOW_UID := $(shell id -u)

.PHONY: up down restart logs ps smoke smoke-task4 reset-keycloak configure-yandex

up:
	mkdir -p airflow/logs
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) down
	$(COMPOSE) up -d --build

logs:
	$(COMPOSE) logs -f --tail=200

ps:
	$(COMPOSE) ps

smoke:
	./scripts/task1-smoke.sh

smoke-task4:
	./scripts/task4-cdc-smoke.sh

reset-keycloak:
	$(COMPOSE) down
	docker run --rm -v "$(PWD):/workspace" alpine sh -c 'rm -rf /workspace/postgres-keycloak-data'
	$(COMPOSE) up -d --build

# После `make up`: задать YANDEX_CLIENT_ID и YANDEX_CLIENT_SECRET (OAuth-приложение Яндекса), затем:
configure-yandex:
	python3 scripts/configure_yandex_idp.py
