-- Release 3: indexes for the slow reports found by scripts/benchmark.py.
-- Each index is justified by a query in scripts/queries.py; see docs/PERFORMANCE.md.

-- Revenue report filters on a date range and sums total_amount.
-- Putting total_amount in the index makes it covering ("Using index"), so MySQL
-- never touches the table rows.
CREATE INDEX idx_orders_purchase_ts_amount
    ON orders (order_purchase_timestamp, total_amount);

-- Customer order history: WHERE customer_id = ? ORDER BY order_purchase_timestamp DESC.
-- Leftmost-prefix rule: this also serves WHERE customer_id = ? on its own, so it can
-- back the foreign key too. It does NOT help a filter on order_purchase_timestamp alone,
-- which is why the index above exists separately.
CREATE INDEX idx_orders_customer_purchase_ts
    ON orders (customer_id, order_purchase_timestamp);

-- High-value payment review: WHERE payment_value > ? ORDER BY payment_value DESC LIMIT n.
CREATE INDEX idx_payments_value
    ON order_payments (payment_value);

-- Customers-by-state dashboard: GROUP BY state becomes an index scan.
CREATE INDEX idx_customers_state
    ON customers (state);
