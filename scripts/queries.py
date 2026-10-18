"""The reports the release gate protects.

critical=True queries fail the pipeline if they regress. budget_ms is a hard ceiling
with generous headroom for slow CI runners; the regression check against the
baseline catches smaller slowdowns.
"""

QUERIES = [
    {
        "name": "monthly_revenue_report",
        "critical": True,
        "budget_ms": 150,
        "why": "Finance report: daily revenue for one month.",
        "sql": """
            SELECT DATE(order_purchase_timestamp) AS day, COUNT(*) AS orders, SUM(total_amount) AS revenue
            FROM orders
            WHERE order_purchase_timestamp >= '2018-03-01' AND order_purchase_timestamp < '2018-04-01'
            GROUP BY day
            ORDER BY day
        """,
    },
    {
        "name": "customer_order_history",
        "critical": True,
        "budget_ms": 50,
        "why": "Support screen: a customer's latest orders.",
        "sql": """
            SELECT order_id, status, order_purchase_timestamp, total_amount
            FROM orders
            WHERE customer_id = 4242
            ORDER BY order_purchase_timestamp DESC
            LIMIT 20
        """,
    },
    {
        "name": "high_value_payments",
        "critical": True,
        "budget_ms": 100,
        "why": "Fraud review queue: largest payments first.",
        "sql": """
            SELECT order_id, payment_type, payment_value
            FROM order_payments
            WHERE payment_value > 1000
            ORDER BY payment_value DESC
            LIMIT 50
        """,
    },
    {
        "name": "customers_by_state",
        "critical": True,
        "budget_ms": 150,
        "why": "Ops dashboard: customer count per state.",
        "sql": """
            SELECT state, COUNT(*) AS customers
            FROM customers
            GROUP BY state
            ORDER BY customers DESC
        """,
    },
    {
        "name": "quarter_revenue_by_state",
        "critical": True,
        "budget_ms": 300,
        "why": "3-table join: Q1 2018 revenue per state.",
        "sql": """
            SELECT c.state, COUNT(DISTINCT o.order_id) AS orders, SUM(p.payment_value) AS revenue
            FROM orders o
            JOIN customers c ON c.customer_id = o.customer_id
            JOIN order_payments p ON p.order_id = o.order_id
            WHERE o.order_purchase_timestamp >= '2018-01-01' AND o.order_purchase_timestamp < '2018-04-01'
            GROUP BY c.state
            ORDER BY revenue DESC
        """,
    },
]
