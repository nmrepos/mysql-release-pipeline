#!/usr/bin/env python3
"""Post-release environment readiness checks. Exit 1 if any check fails."""
import re
import sys
from pathlib import Path

from db import connect

MIGRATIONS = Path(__file__).resolve().parent.parent / "db" / "migrations"
EXPECTED_INDEXES = {
    ("orders", "idx_orders_purchase_ts_amount"),
    ("orders", "idx_orders_customer_purchase_ts"),
    ("order_payments", "idx_payments_value"),
    ("customers", "idx_customers_state"),
}
EXPECTED_COLUMNS = {("orders", "source"), ("customers", "lifetime_orders")}
MIN_ROWS = {"customers": 100_000, "orders": 120_000, "order_payments": 120_000, "order_reviews": 80_000}


def latest_file_version():
    versions = [int(re.match(r"V(\d+)__", p.name).group(1)) for p in MIGRATIONS.glob("V*__*.sql")]
    return max(versions)


def main():
    conn = connect()
    cur = conn.cursor()
    db = conn.database
    checks = []

    def check(name, ok, detail=""):
        checks.append(ok)
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}{': ' + str(detail) if detail else ''}")

    print("Release validation")

    cur.execute("SELECT version, description, success FROM flyway_schema_history "
                "WHERE version IS NOT NULL ORDER BY installed_rank")
    history = cur.fetchall()
    failed = [h for h in history if not h[2]]
    check("no failed migrations in flyway_schema_history", not failed, failed or f"{len(history)} applied")
    applied = max(int(h[0]) for h in history) if history else 0
    expected = latest_file_version()
    check("database is at the latest migration", applied == expected, f"db v{applied}, repo v{expected}")

    cur.execute("SELECT table_name, index_name FROM information_schema.statistics WHERE table_schema = %s", (db,))
    indexes = {(t, i) for t, i in cur.fetchall()}
    missing = EXPECTED_INDEXES - indexes
    check("reporting indexes exist", not missing, sorted(missing) or "")

    cur.execute("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = %s", (db,))
    columns = {(t, c) for t, c in cur.fetchall()}
    missing = EXPECTED_COLUMNS - columns
    check("release 4 columns exist", not missing, sorted(missing) or "")

    for table, minimum in MIN_ROWS.items():
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        n = cur.fetchone()[0]
        check(f"{table} has >= {minimum:,} rows", n >= minimum, f"{n:,}")

    cur.execute("SELECT COUNT(*) FROM order_payments p LEFT JOIN orders o ON o.order_id = p.order_id "
                "WHERE o.order_id IS NULL")
    check("no orphan payments", cur.fetchone()[0] == 0)

    cur.execute("SELECT COUNT(*) FROM orders o LEFT JOIN order_payments p ON p.order_id = o.order_id "
                "WHERE p.payment_id IS NULL")
    check("every order has a payment", cur.fetchone()[0] == 0)

    cur.close()
    conn.close()
    if not all(checks):
        sys.exit(1)
    print("All release checks passed.")


if __name__ == "__main__":
    main()
