# Finding: deadlocks in the order transaction

## What the test does

`scripts/concurrency_test.py` runs 16 threads, each with its own connection, doing 250
random operations: 40% place an order (a transaction), 40% reads, 20% status updates.
Orders go to a small set of 10 "hot" customers on purpose, so threads compete for the
same rows the way a popular account or a flash sale would.

Afterwards it checks the data, not just the error count:
1. orders created by the run == transactions the threads saw commit
2. each of those orders has exactly one payment, equal to its total
3. each hot customer's `lifetime_orders` went up by exactly its committed orders (no lost updates)

## What it found

The first version of `place_order` was written in the obvious order:

```sql
INSERT INTO orders (customer_id, ...) VALUES (5, ...);      -- FK check
INSERT INTO order_payments (...) VALUES (...);
UPDATE customers SET lifetime_orders = lifetime_orders + 1 WHERE customer_id = 5;
COMMIT;
```

With 16 threads this caused **131 to 232 deadlocks per run** (`ER_LOCK_DEADLOCK`, 1213).
The retry logic hid them, so there were 0 errors and the invariants held. A
single-threaded test would never have shown them.

`SHOW ENGINE INNODB STATUS` showed why:

```
*** (1) TRANSACTION:
UPDATE customers SET lifetime_orders = lifetime_orders + 1 WHERE customer_id = 5
*** (1) HOLDS THE LOCK(S):
... index PRIMARY of table `shop`.`customers` ... lock mode S locks rec but not gap
*** (2) TRANSACTION:
UPDATE customers SET lifetime_orders = lifetime_orders + 1 WHERE customer_id = 5
*** (2) HOLDS THE LOCK(S):
... index PRIMARY of table `shop`.`customers` ... lock mode S locks rec but not gap
*** WE ROLL BACK TRANSACTION (2)
```

The `INSERT INTO orders` checks the foreign key, which puts a **shared (S) lock** on
the parent customer row. Two transactions for the same customer can both hold that S
lock. Then each one's `UPDATE` needs an **exclusive (X) lock** on that row and waits for
the other to release its S lock. Neither can continue, so InnoDB kills one.

## Fix

Take the exclusive lock first: run the `UPDATE customers` at the start of the
transaction. The second transaction now waits at its first statement instead of
deadlocking halfway through.

| Lock order | Deadlock retries (4,000 ops) | Errors | Invariants |
|---|---:|---:|---|
| INSERT, INSERT, UPDATE (naive) | 131–232 | 0 | pass |
| UPDATE, INSERT, INSERT (fixed) | 0 | 0 | pass |

Reproduce both with `make deadlock-demo` and `make concurrency`.

Retrying on 1213/1205 is still kept. Deadlocks can't be ruled out completely in a
busy database, so the application has to handle them. Lowering how often they happen
is the real fix.
