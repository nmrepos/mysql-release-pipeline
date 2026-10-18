PY ?= python3
REPORTS := reports

.PHONY: up down reset migrate-previous seed bench-baseline migrate bench-release

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

bench-baseline:
	$(PY) scripts/benchmark.py --label baseline --out $(REPORTS)/baseline.json

migrate:
	scripts/flyway.sh migrate
	scripts/flyway.sh validate
	scripts/flyway.sh info

bench-release:
	$(PY) scripts/benchmark.py --label release --out $(REPORTS)/release.json
