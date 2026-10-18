-- BREAK-IT DRILL ONLY. Never copy this into db/migrations.
-- Simulates a "cleanup" release that drops an index a report depends on.
-- `make drill` applies it on top of the real migrations, re-runs the benchmark
-- and the regression gate should fail on monthly_revenue_report.
DROP INDEX idx_orders_purchase_ts_amount ON orders;
