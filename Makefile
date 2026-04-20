COMPOSE = docker compose

.PHONY: up down restart logs ps smoke reset-keycloak

up:
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

reset-keycloak:
	$(COMPOSE) down
	docker run --rm -v "$(PWD):/workspace" alpine sh -c 'rm -rf /workspace/postgres-keycloak-data'
	$(COMPOSE) up -d --build
