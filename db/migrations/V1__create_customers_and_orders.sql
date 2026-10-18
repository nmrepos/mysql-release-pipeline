-- Release 1: core ordering schema.
CREATE TABLE customers (
    customer_id  INT UNSIGNED NOT NULL AUTO_INCREMENT,
    full_name    VARCHAR(100) NOT NULL,
    city         VARCHAR(60)  NOT NULL,
    state        CHAR(2)      NOT NULL,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (customer_id)
) ENGINE=InnoDB;

CREATE TABLE orders (
    order_id                 BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    customer_id              INT UNSIGNED    NOT NULL,
    status                   VARCHAR(20)     NOT NULL,
    order_purchase_timestamp DATETIME        NOT NULL,
    total_amount             DECIMAL(10,2)   NOT NULL,
    PRIMARY KEY (order_id),
    CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
) ENGINE=InnoDB;
