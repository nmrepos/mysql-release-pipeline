-- Release 2: payments and reviews.
CREATE TABLE order_payments (
    payment_id    BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    order_id      BIGINT UNSIGNED NOT NULL,
    payment_type  VARCHAR(20)     NOT NULL,
    installments  TINYINT UNSIGNED NOT NULL DEFAULT 1,
    payment_value DECIMAL(10,2)   NOT NULL,
    PRIMARY KEY (payment_id),
    CONSTRAINT fk_payments_order FOREIGN KEY (order_id) REFERENCES orders (order_id)
) ENGINE=InnoDB;

CREATE TABLE order_reviews (
    review_id    BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    order_id     BIGINT UNSIGNED NOT NULL,
    review_score TINYINT UNSIGNED NOT NULL,
    review_comment VARCHAR(255) NULL,
    created_at   DATETIME NOT NULL,
    PRIMARY KEY (review_id),
    CONSTRAINT fk_reviews_order FOREIGN KEY (order_id) REFERENCES orders (order_id)
) ENGINE=InnoDB;
