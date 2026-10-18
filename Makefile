PY ?= python3
REPORTS := reports

.PHONY: up down reset check migrate-previous seed bench-baseline migrate bench-release gate concurrency deadlock-demo

up:
	docker compose up -d --wait

down:
	docker compose down -v

reset: down up

check:
	$(PY) -m pytest -q tests

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

gate:
	$(PY) scripts/compare.py $(REPORTS)/baseline.json $(REPORTS)/release.json --markdown $(REPORTS)/benchmark.md

concurrency:
	$(PY) scripts/concurrency_test.py --out $(REPORTS)/concurrency.json

deadlock-demo:
	$(PY) scripts/concurrency_test.py --lock-order naive --out $(REPORTS)/concurrency-naive.json
