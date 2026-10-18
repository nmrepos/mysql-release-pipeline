#!/usr/bin/env bash
# Break-it drill: "after a release, a report that was fast is now slow".
# Needs a database at the released version and reports/release.json (run `make release`).
# Leaves the schema history at v6 (drill migrations), so run `make reset` afterwards.
set -uo pipefail
cd "$(dirname "$0")/.."

echo "== 1. Ship a bad release: V5 drops idx_orders_purchase_ts_amount"
FLYWAY_EXTRA_LOCATIONS=drills/regression scripts/flyway.sh migrate >/dev/null || exit 1

echo "== 2. Benchmark the bad release and run the gate (it should FAIL)"
python3 scripts/benchmark.py --label bad-release --out reports/drill-bad.json || exit 1
if python3 scripts/compare.py reports/release.json reports/drill-bad.json --markdown reports/drill-bad.md; then
  echo "DRILL FAILED: the gate did not catch the dropped index" >&2
  exit 1
fi
echo "   -> gate caught the regression (expected)"

echo "== 3. Fix forward: V6 recreates the index (never edit V5, it already ran)"
FLYWAY_EXTRA_LOCATIONS=drills/regression,drills/fix scripts/flyway.sh migrate >/dev/null || exit 1

echo "== 4. Re-run the same benchmark to prove the fix"
python3 scripts/benchmark.py --label fixed --out reports/drill-fixed.json || exit 1
python3 scripts/compare.py reports/release.json reports/drill-fixed.json --markdown reports/drill-fixed.md || exit 1
echo "Drill complete: regression detected, fixed forward, verified."
