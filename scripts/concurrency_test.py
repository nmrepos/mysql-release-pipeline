#!/usr/bin/env python3
"""Concurrent INSERT / SELECT / UPDATE load against the released schema.

Each worker thread has its own connection and runs a random mix of:
  * place_order  (transaction): INSERT order, INSERT payment, UPDATE the customer's
    lifetime_orders counter. Customers come from a small "hot" set on purpose, so
    threads fight over the same rows and real lock waits / deadlocks happen.
  * read         : customer order history + the monthly revenue report.
  * update_status: UPDATE a random order's status.

Deadlocks (1213) and lock wait timeouts (1205) are rolled back and retried, which is
what a well-behaved application does. Anything else, or running out of retries, is an
error. After the run, invariants are checked against the database:
  1. orders created by this run == transactions the threads saw commit
  2. every one of those orders has exactly one payment, equal to its total
  3. hot customers' lifetime_orders went up by exactly the committed count
     (catches lost updates)
Exit code is 1 if there were errors or any invariant failed.
"""
import argparse
import json
import random
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

import mysql.connector
from mysql.connector import errorcode

from db import connect

RETRYABLE = {errorcode.ER_LOCK_DEADLOCK, errorcode.ER_LOCK_WAIT_TIMEOUT}
MAX_RETRIES = 5


class Stats:
    def __init__(self):
        self.lock = threading.Lock()
        self.counts = {"place_order": 0, "read": 0, "update_status": 0}
        self.retries = 0
        self.errors = []
        self.committed_by_customer = {}

    def ok(self, op, customer_id=None):
        with self.lock:
            self.counts[op] += 1
            if customer_id is not None:
                self.committed_by_customer[customer_id] = self.committed_by_customer.get(customer_id, 0) + 1

    def retry(self):
        with self.lock:
            self.retries += 1

    def error(self, op, exc):
        with self.lock:
            self.errors.append(f"{op}: {exc}")


def place_order(conn, cur, rng, ctx):
    customer_id = rng.choice(ctx["hot_customers"])
    amount = Decimal(rng.randint(500, 50000)) / 100
    cur.execute(
        "INSERT INTO orders (customer_id, status, order_purchase_timestamp, total_amount, source) "
        "VALUES (%s, 'processing', NOW(), %s, %s)",
        (customer_id, amount, ctx["source"]),
    )
    order_id = cur.lastrowid
    cur.execute(
        "INSERT INTO order_payments (order_id, payment_type, installments, payment_value) "
        "VALUES (%s, 'credit_card', 1, %s)",
        (order_id, amount),
    )
    cur.execute("UPDATE customers SET lifetime_orders = lifetime_orders + 1 WHERE customer_id = %s",
                (customer_id,))
    conn.commit()
    return customer_id


def read(conn, cur, rng, ctx):
    cur.execute(
        "SELECT order_id, status, total_amount FROM orders WHERE customer_id = %s "
        "ORDER BY order_purchase_timestamp DESC LIMIT 20",
        (rng.choice(ctx["hot_customers"]),),
    )
    cur.fetchall()
    cur.execute(
        "SELECT DATE(order_purchase_timestamp) d, COUNT(*), SUM(total_amount) FROM orders "
        "WHERE order_purchase_timestamp >= '2018-03-01' AND order_purchase_timestamp < '2018-04-01' GROUP BY d"
    )
    cur.fetchall()
    conn.commit()


def update_status(conn, cur, rng, ctx):
    cur.execute("UPDATE orders SET status = %s WHERE order_id = %s",
                (rng.choice(["shipped", "delivered"]), rng.randint(1, ctx["max_order_id"])))
    conn.commit()


OPS = [(place_order, "place_order", 0.4), (read, "read", 0.4), (update_status, "update_status", 0.2)]


def worker(worker_id, ops, seed, ctx, stats):
    rng = random.Random(seed + worker_id)
    conn = connect(autocommit=False)
    cur = conn.cursor()
    try:
        for _ in range(ops):
            fn, name, _w = rng.choices(OPS, [w for *_x, w in OPS])[0]
            for attempt in range(MAX_RETRIES + 1):
                try:
                    result = fn(conn, cur, rng, ctx)
                    stats.ok(name, result if name == "place_order" else None)
                    break
                except mysql.connector.Error as exc:
                    conn.rollback()
                    if exc.errno in RETRYABLE and attempt < MAX_RETRIES:
                        stats.retry()
                        time.sleep(0.01 * (2 ** attempt) * rng.random())
                        continue
                    stats.error(name, exc)
                    break
    finally:
        cur.close()
        conn.close()


def check_invariants(ctx, before_counters, stats):
    conn = connect()
    cur = conn.cursor()
    failures = []
    committed = sum(stats.committed_by_customer.values())

    cur.execute("SELECT COUNT(*) FROM orders WHERE source = %s", (ctx["source"],))
    created = cur.fetchone()[0]
    if created != committed:
        failures.append(f"orders created by run = {created}, but threads committed {committed}")

    cur.execute(
        "SELECT o.order_id, o.total_amount, COUNT(p.payment_id), COALESCE(SUM(p.payment_value), 0) "
        "FROM orders o LEFT JOIN order_payments p ON p.order_id = o.order_id "
        "WHERE o.source = %s GROUP BY o.order_id, o.total_amount "
        "HAVING COUNT(p.payment_id) <> 1 OR COALESCE(SUM(p.payment_value), 0) <> o.total_amount",
        (ctx["source"],),
    )
    bad = cur.fetchall()
    if bad:
        failures.append(f"{len(bad)} orders without exactly one matching payment, e.g. {bad[:3]}")

    after = counters(cur, ctx["hot_customers"])
    for cid in ctx["hot_customers"]:
        expected = before_counters[cid] + stats.committed_by_customer.get(cid, 0)
        if after[cid] != expected:
            failures.append(f"customer {cid}: lifetime_orders {after[cid]}, expected {expected} (lost update)")

    cur.close()
    conn.close()
    return failures


def counters(cur, customer_ids):
    placeholders = ",".join(["%s"] * len(customer_ids))
    cur.execute(f"SELECT customer_id, lifetime_orders FROM customers WHERE customer_id IN ({placeholders})",
                customer_ids)
    return dict(cur.fetchall())


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--threads", type=int, default=16)
    parser.add_argument("--ops-per-thread", type=int, default=250)
    parser.add_argument("--hot-customers", type=int, default=10)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", default="reports/concurrency.json")
    args = parser.parse_args()

    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT MAX(order_id) FROM orders")
    ctx = {
        "source": "lt-" + uuid.uuid4().hex[:8],
        "hot_customers": list(range(1, args.hot_customers + 1)),
        "max_order_id": cur.fetchone()[0],
    }
    before_counters = counters(cur, ctx["hot_customers"])
    cur.close()
    conn.close()

    stats = Stats()
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.threads) as pool:
        for i in range(args.threads):
            pool.submit(worker, i, args.ops_per_thread, args.seed, ctx, stats)
    elapsed = time.perf_counter() - started

    failures = check_invariants(ctx, before_counters, stats)
    total_ops = sum(stats.counts.values())
    report = {
        "run_source_tag": ctx["source"],
        "threads": args.threads,
        "ops_attempted": args.threads * args.ops_per_thread,
        "ops_succeeded": total_ops,
        "by_operation": stats.counts,
        "deadlock_or_lock_wait_retries": stats.retries,
        "errors": stats.errors,
        "invariant_failures": failures,
        "seconds": round(elapsed, 2),
        "ops_per_second": round(total_ops / elapsed, 1),
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2))

    print(f"{args.threads} threads, {total_ops}/{report['ops_attempted']} ops in {elapsed:.1f}s "
          f"({report['ops_per_second']} ops/s)")
    print(f"  by operation: {stats.counts}")
    print(f"  deadlock / lock-wait retries: {stats.retries}")
    print(f"  errors: {len(stats.errors)}")
    for e in stats.errors[:10]:
        print(f"    {e}")
    print(f"  invariants: {'all passed' if not failures else 'FAILED'}")
    for f in failures:
        print(f"    {f}")

    if stats.errors or failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
