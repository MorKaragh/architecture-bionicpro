COMPOSE = docker compose
export AIRFLOW_UID := $(shell id -u)

# Каталоги с данными на хосте (bind mounts из docker-compose) + логи Airflow
DATA_DIRS := postgres-keycloak-data postgres-app-data postgres-sources-data postgres-airflow-data clickhouse-data minio-data airflow/logs

.PHONY: up down restart logs ps smoke smoke-task4 reset-keycloak configure-yandex clean-data up-clean seed-sources-demo patch-clickhouse-mv-crm

up:
	mkdir -p airflow/logs
	$(COMPOSE) up -d --build

# Остановка контейнеров, снятие именованных томов (compose volumes), удаление локальных данных — как после свежего git clone
clean-data:
	$(COMPOSE) down -v
	docker run --rm -v "$(CURDIR):/workspace" alpine:3.20 sh -c 'rm -rf $(addprefix /workspace/,$(DATA_DIRS)) /workspace/airflow/dags/__pycache__'

# Чистый запуск для ревью и отладки (в т.ч. когда в UI Airflow не видны DAG)
up-clean: clean-data
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

# Демо-строки CRM/телеметрии для prothetic1 (если БД sources поднималась до добавления строк в init-sources.sql)
seed-sources-demo:
	cat scripts/seed-sources-demo-users.sql | $(COMPOSE) exec -T sources_db psql -U sources_user -d sources_db -v ON_ERROR_STOP=1 -f -

# Пересоздать MV CRM→витрина (стабильный data_as_of по телеметрии; без этого CDN почти всегда MISS на /reports-cache)
patch-clickhouse-mv-crm:
	./scripts/clickhouse-recreate-mv-crm-data-as-of.sh

reset-keycloak:
	$(COMPOSE) down
	docker run --rm -v "$(PWD):/workspace" alpine sh -c 'rm -rf /workspace/postgres-keycloak-data'
	$(COMPOSE) up -d --build

# После `make up`: задать YANDEX_CLIENT_ID и YANDEX_CLIENT_SECRET (OAuth-приложение Яндекса), затем:
configure-yandex:
	python3 scripts/configure_yandex_idp.py
