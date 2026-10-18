#!/usr/bin/env python3
"""Seed the shop schema with a deterministic synthetic e-commerce dataset.

Default size is about 430,000 rows: 100k customers, 120k orders, ~126k payments
and ~84k reviews. The same --seed always produces the same data, so benchmark
runs are comparable.

Only uses columns from releases 1 and 2, so it can run before later migrations.
"""
import argparse
import random
import time
from datetime import datetime, timedelta

from db import connect

STATES = ["SP", "RJ", "MG", "RS", "PR", "SC", "BA", "DF", "GO", "ES", "PE", "CE", "PA", "MT"]
STATE_WEIGHTS = [42, 13, 12, 6, 5, 4, 3, 2, 2, 2, 2, 1, 1, 1]
CITIES = ["Centro", "Norte", "Sul", "Leste", "Oeste", "Jardim", "Vila Nova", "Porto"]
STATUSES = ["delivered", "delivered", "delivered", "delivered", "shipped", "processing", "canceled"]
PAYMENT_TYPES = ["credit_card", "credit_card", "credit_card", "boleto", "voucher", "debit_card"]
COMMENTS = [None, None, "great product", "arrived late", "as described", "would buy again", "damaged box"]

START = datetime(2016, 1, 1)
SPAN_SECONDS = int((datetime(2019, 1, 1) - START).total_seconds())
BATCH = 5000


def insert_batches(cur, sql, rows):
    for i in range(0, len(rows), BATCH):
        cur.executemany(sql, rows[i:i + BATCH])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--customers", type=int, default=100_000)
    parser.add_argument("--orders", type=int, default=120_000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    conn = connect()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM orders")
    if cur.fetchone()[0] > 0:
        raise SystemExit("orders already has data; refusing to seed twice (reset the database first)")

    started = time.perf_counter()

    customers = [
        (f"Customer {i}", rng.choice(CITIES), rng.choices(STATES, STATE_WEIGHTS)[0],
         START + timedelta(seconds=rng.randrange(SPAN_SECONDS)))
        for i in range(1, args.customers + 1)
    ]
    insert_batches(cur, "INSERT INTO customers (full_name, city, state, created_at) VALUES (%s, %s, %s, %s)",
                   customers)

    orders, payments, reviews = [], [], []
    for order_id in range(1, args.orders + 1):
        purchased = START + timedelta(seconds=rng.randrange(SPAN_SECONDS))
        # Log-normal amounts: most orders are small, about 1% are over 1,000.
        total = round(min(rng.lognormvariate(4.6, 1.0), 15000), 2)
        orders.append((order_id, rng.randint(1, args.customers), rng.choice(STATUSES), purchased, total))

        if rng.random() < 0.05:  # split payment
            first = round(total * rng.uniform(0.2, 0.8), 2)
            payments.append((order_id, "voucher", 1, first))
            payments.append((order_id, rng.choice(PAYMENT_TYPES), rng.randint(1, 10), round(total - first, 2)))
        else:
            payments.append((order_id, rng.choice(PAYMENT_TYPES), rng.randint(1, 10), total))

        if rng.random() < 0.7:
            reviews.append((order_id, rng.choices([1, 2, 3, 4, 5], [10, 3, 8, 20, 59])[0], rng.choice(COMMENTS),
                            purchased + timedelta(days=rng.randint(3, 30))))

    insert_batches(cur, "INSERT INTO orders (order_id, customer_id, status, order_purchase_timestamp, total_amount) "
                        "VALUES (%s, %s, %s, %s, %s)", orders)
    insert_batches(cur, "INSERT INTO order_payments (order_id, payment_type, installments, payment_value) "
                        "VALUES (%s, %s, %s, %s)", payments)
    insert_batches(cur, "INSERT INTO order_reviews (order_id, review_score, review_comment, created_at) "
                        "VALUES (%s, %s, %s, %s)", reviews)
    conn.commit()

    for table in ("customers", "orders", "order_payments", "order_reviews"):
        cur.execute(f"ANALYZE TABLE {table}")
        cur.fetchall()

    total_rows = len(customers) + len(orders) + len(payments) + len(reviews)
    print(f"Seeded {len(customers):,} customers, {len(orders):,} orders, {len(payments):,} payments, "
          f"{len(reviews):,} reviews = {total_rows:,} rows in {time.perf_counter() - started:.1f}s")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
