PY ?= python3
REPORTS := reports

.PHONY: up down reset migrate

up:
	docker compose up -d --wait

down:
	docker compose down -v

reset: down up

migrate:
	scripts/flyway.sh migrate
	scripts/flyway.sh validate
	scripts/flyway.sh info
