-- BREAK-IT DRILL ONLY. The fix-forward for V5: recreate the index in a NEW migration
-- instead of editing or deleting V5 (which has already run).
CREATE INDEX idx_orders_purchase_ts_amount
    ON orders (order_purchase_timestamp, total_amount);
