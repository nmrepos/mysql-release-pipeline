-- Release 4: backward-compatible "expand" change.
-- Both columns are NOT NULL with a default, so code from release 3 keeps working
-- (it never mentions them) while the new code starts writing them.
ALTER TABLE orders
    ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'web';

ALTER TABLE customers
    ADD COLUMN lifetime_orders INT UNSIGNED NOT NULL DEFAULT 0;
