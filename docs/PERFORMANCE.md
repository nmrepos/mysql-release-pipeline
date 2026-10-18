# Query performance: what was slow, what was indexed, and why

## Method

1. **Measure first.** `scripts/benchmark.py` runs each report in `scripts/queries.py`
   once to warm the buffer pool, then 7 more times, and keeps the median.
2. **Read the plan.** For each query it stores the `EXPLAIN` row: `type`, `key`, `rows`, `Extra`.
   Warning signs: `type = ALL` (full table scan), a `rows` estimate close to the table
   size, `Using filesort` / `Using temporary`.
3. **Change one thing.** Each index in `V3__add_reporting_indexes.sql` targets one query.
4. **Measure again** with the same script, on the same data (the seed is deterministic).
   The pipeline does this on every run: benchmark at v2, migrate, benchmark at v4, compare.

## Baseline (schema v2, no secondary indexes except the foreign keys)

| Query | Median | type | key | rows | Extra |
|---|---:|---|---|---:|---|
| monthly_revenue_report | 23.5 ms | ALL | – | 119,834 | Using where; Using temporary; Using filesort |
| customer_order_history | 0.3 ms | ref | fk_orders_customer | 3 | Using filesort |
| high_value_payments | 26.8 ms | ALL | – | 125,882 | Using where; Using filesort |
| customers_by_state | 31.0 ms | ALL | – | 99,864 | Using temporary; Using filesort |
| quarter_revenue_by_state | 87.4 ms | ALL | – | 119,834 | Using where; Using temporary; Using filesort |

## The indexes (V3) and the reasoning

### `idx_orders_purchase_ts_amount (order_purchase_timestamp, total_amount)`
The revenue report filters one month out of three years (~3% of orders) and sums
`total_amount`. An index on the timestamp turns the scan into a `range`. Adding
`total_amount` as the second column makes it a **covering index** (`Using index`):
every column the query needs is in the index, so MySQL never reads the table rows.

**23.5 ms → 2.7 ms**, rows examined 119,834 → 3,422.

### `idx_payments_value (payment_value)`
`WHERE payment_value > 1000 ORDER BY payment_value DESC LIMIT 50`. B-tree indexes are
sorted, so MySQL walks the index backwards from the top, stops after 50 matches and
needs no sort at all (`Backward index scan`, no `Using filesort`).

**26.8 ms → 0.8 ms.**

### `idx_customers_state (state)`
`GROUP BY state` over every customer. It still has to read all 100k entries
(`type = index`), but the index is much smaller than the table and already grouped.

**31.0 ms → 16.3 ms.** A modest gain, because the query still reads every customer.

### `idx_orders_customer_purchase_ts (customer_id, order_purchase_timestamp)`
The support screen: `WHERE customer_id = ? ORDER BY order_purchase_timestamp DESC LIMIT 20`.
It was already fast through the foreign key index, but needed `Using filesort`.
With the composite index the rows come out already sorted (`Backward index scan`).
Customers here only have a few orders, so the time doesn't change (0.3 ms either way).
The gain is that the query no longer needs a sort, so it stays fast for a customer
with thousands of orders.

## The leftmost-prefix rule, shown with real EXPLAIN output

A composite index on `(customer_id, order_purchase_timestamp)` is sorted by
`customer_id` first. It can seek on `customer_id`, or on `customer_id` + a timestamp
range, but **not** on the timestamp alone:

```
-- timestamp only, with the timestamp index hidden: only the composite is left
EXPLAIN SELECT COUNT(*) FROM orders IGNORE INDEX (idx_orders_purchase_ts_amount)
WHERE order_purchase_timestamp >= '2018-03-01' AND order_purchase_timestamp < '2018-04-01';
  type=index  key=idx_orders_customer_purchase_ts  rows=119,814    <- reads the whole index

-- customer_id + timestamp: uses the leftmost column, so it can seek
EXPLAIN SELECT COUNT(*) FROM orders
WHERE customer_id = 4242 AND order_purchase_timestamp >= '2018-01-01';
  type=range  key=idx_orders_customer_purchase_ts  rows=1
```

That is why the revenue report needs its own index that starts with the timestamp.
Because the composite index starts with `customer_id`, InnoDB can also use it to back
the `fk_orders_customer` foreign key.

## What did not improve, and why

- **`quarter_revenue_by_state` (3-table join): 87 ms → 103 ms, roughly no change
  (noise).** The plan improved from `ALL` to a `range` of 18,272 orders, but each of
  those orders then needs a primary-key lookup into `customers` and a lookup into
  `order_payments`, about 36k random lookups. The index removed the cheap part, the scan,
  but not the expensive part, the lookups. Real options would be a covering index
  `(order_purchase_timestamp, customer_id)` to avoid reading the order rows, or a
  pre-aggregated daily revenue table for reporting. Neither is done yet.
- **`customer_order_history`**: already fast; see above.

## Trade-offs

Indexes are not free:
- Every INSERT/UPDATE on `orders` now maintains 3 secondary indexes instead of 1.
- They use disk and buffer-pool memory.
- Building them on 430k rows took under a second here, but on a large production table
  `CREATE INDEX` takes a long time and should be planned (MySQL 8 builds them online
  with `ALGORITHM=INPLACE, LOCK=NONE`, but it still adds I/O load).

So each index here is tied to a named query in `queries.py`, and the gate keeps
measuring those queries on every release.
