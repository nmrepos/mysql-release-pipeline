# MySQL Release Pipeline

A CI/CD release pipeline for a MySQL 8.0 database. Every schema change is a versioned
Flyway migration, and a release only passes after it has been applied to a seeded
430k-row database and has passed a query-performance gate, a multi-threaded
INSERT/SELECT/UPDATE test with data-integrity checks, and environment readiness checks.

```
 push / PR
    │
    ▼
┌───────────────────────── migration-guard ─────────────────────────┐
│ naming + continuous versions · released migrations must not change │
│ unit tests for the gate and the guard                              │
└───────────────────────────────┬────────────────────────────────────┘
                                ▼
┌──────────────── release-validation (MySQL 8.0 service) ───────────┐
│ 1. flyway migrate -target=2      "what production runs today"     │
│ 2. seed ~430k rows               deterministic synthetic data     │
│ 3. benchmark + EXPLAIN           baseline                         │
│ 4. flyway migrate / validate     apply this release (V3, V4)      │
│ 5. benchmark + EXPLAIN           release                          │
│ 6. performance gate              fail on regression or budget     │
│ 7. concurrency test              16 threads, invariants checked   │
│ 8. readiness checks              history, indexes, columns, data  │
│ 9. break-it drill                prove the gate catches a bad index│
└────────────────────────────────────────────────────────────────────┘
   any failing step stops the release; reports are uploaded as artifacts
```

## Results (local run, MySQL 8.0, 430,169 rows)

| Query | Before | After | Plan before → after |
|---|---:|---:|---|
| `monthly_revenue_report` | 23.5 ms | 2.7 ms | `ALL`, 119,834 rows → `range` on covering `idx_orders_purchase_ts_amount`, 3,422 rows |
| `high_value_payments` | 26.8 ms | 0.8 ms | `ALL` + filesort, 125,882 rows → `range` on `idx_payments_value`, 1,198 rows, no filesort |
| `customers_by_state` | 31.0 ms | 16.3 ms | `ALL` → `index` scan on `idx_customers_state` (covering) |
| `customer_order_history` | 0.3 ms | 0.5 ms | `ref` + **Using filesort** → `ref` + backward index scan, no filesort |
| `quarter_revenue_by_state` | 87 ms | 103 ms | `ALL` → `range`, but cost is the 18k primary-key lookups per join, so no real gain |

Timings are medians of 7 runs and change a little between runs. The plans don't.
Two queries did **not** get faster, and [docs/PERFORMANCE.md](docs/PERFORMANCE.md)
explains why instead of hiding them.

Concurrency test: 16 threads, 4,000 mixed operations, **0 errors, 0 deadlock retries,
all invariants hold**. The first version of the order transaction hit **131–232 deadlocks
per run**. The cause and the fix are in [docs/CONCURRENCY.md](docs/CONCURRENCY.md).

## Repository layout

| Path | What it is |
|---|---|
| `db/migrations/V1..V4__*.sql` | The versioned schema history (Flyway) |
| `scripts/flyway.sh` | Runs the Flyway CLI from its Docker image, same command locally and in CI |
| `scripts/seed.py` | Deterministic data generator (100k customers, 120k orders, ~126k payments, ~84k reviews) |
| `scripts/queries.py` | The critical reports the gate protects, with time budgets |
| `scripts/benchmark.py` | Warm-up + median-of-N timing, captures `EXPLAIN` for each query |
| `scripts/compare.py` | Performance gate: fails on >50% **and** >10 ms regression, or over budget |
| `scripts/concurrency_test.py` | Multi-threaded load with deadlock retry and post-run invariant checks |
| `scripts/validate.py` | Readiness checks: Flyway history, expected indexes/columns, row counts, orphans |
| `scripts/check_migrations.py` | Pre-merge guard: naming, gaps, and "never edit a released migration" |
| `scripts/drill.sh`, `drills/` | Break-it drill: a release that drops an index, then the fix-forward |
| `.github/workflows/release-pipeline.yml` | The pipeline |
| `docs/` | Performance notes, concurrency finding, runbook |

## Run it locally

Needs Docker, Python 3.10+ and `make`.

```bash
pip install -r requirements.txt
make up          # MySQL 8.0 in Docker
make release     # the whole pipeline, same steps as CI
make drill       # break-it drill (run `make reset` afterwards)
make deadlock-demo   # reproduce the deadlocks with the old lock order
```

Flyway runs in a container on the host network. On Docker Desktop (macOS/Windows)
point it at the compose network instead:
`export FLYWAY_NETWORK=mysql-release-pipeline_default FLYWAY_DB_HOST=mysql`.

Connection settings come from `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
(defaults match `docker-compose.yml`). In CI the password can come from the
`DB_PASSWORD` repository secret.

## Docs

- [docs/PERFORMANCE.md](docs/PERFORMANCE.md): how the slow queries were found, what was indexed and why, the leftmost-prefix rule with real EXPLAIN output, and the trade-offs
- [docs/CONCURRENCY.md](docs/CONCURRENCY.md): the FK shared-lock deadlock the multi-threaded test exposed
- [docs/RUNBOOK.md](docs/RUNBOOK.md): checksum mismatch, a migration failing halfway, rollback strategy, "a report got slow after a release"
