PY ?= python3
REPORTS := reports

.PHONY: up down reset migrate-previous seed migrate

up:
	docker compose up -d --wait

down:
	docker compose down -v

reset: down up

# Simulates the schema currently in production (release 2) before this release is applied.
migrate-previous:
	scripts/flyway.sh migrate -target=2

seed:
	$(PY) scripts/seed.py

migrate:
	scripts/flyway.sh migrate
	scripts/flyway.sh validate
	scripts/flyway.sh info
