PY ?= python3
REPORTS := reports

.PHONY: help up down reset check migrate-previous seed bench-baseline migrate bench-release gate \
        concurrency deadlock-demo validate release drill

help:
	@echo "make up            start local MySQL (docker compose)"
	@echo "make release       full pipeline: previous release -> seed -> benchmark -> migrate -> gate -> concurrency -> validate"
	@echo "make drill         break-it drill: ship a release that drops an index and watch the gate catch it"
	@echo "make deadlock-demo run the concurrency test with the old lock order to reproduce deadlocks"
	@echo "make check         migration naming/history guard + unit tests (no database needed)"
	@echo "make reset         wipe the local database"

up:
	docker compose up -d --wait

down:
	docker compose down -v

reset: down up

check:
	$(PY) scripts/check_migrations.py
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

validate:
	$(PY) scripts/validate.py

release: check migrate-previous seed bench-baseline migrate bench-release gate concurrency validate

drill:
	scripts/drill.sh
