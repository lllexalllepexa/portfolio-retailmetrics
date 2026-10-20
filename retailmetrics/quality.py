"""In-pipeline data quality gates. Each check is a SQL query returning the number of offending rows."""

from __future__ import annotations

import logging

import duckdb

log = logging.getLogger(__name__)

PRIMARY_KEYS: dict[str, str] = {
    "customers": "customer_id",
    "products": "product_id",
    "orders": "order_id",
    "order_items": "order_line_id",
}

# (child table, child column, parent table, parent column)
FOREIGN_KEYS: list[tuple[str, str, str, str]] = [
    ("orders", "customer_id", "customers", "customer_id"),
    ("order_items", "order_id", "orders", "order_id"),
    ("order_items", "product_id", "products", "product_id"),
]

BUSINESS_RULES: dict[str, str] = {
    "orders.status outside allowed values": """
        SELECT count(*) FROM orders
        WHERE status IS NULL OR status NOT IN ('completed', 'returned', 'cancelled')""",
    "orders.order_date before customers.signup_date": """
        SELECT count(*) FROM orders AS o
        JOIN customers AS c ON o.customer_id = c.customer_id
        WHERE o.order_date < c.signup_date""",
    "orders without line items": """
        SELECT count(*) FROM orders AS o
        ANTI JOIN order_items AS oi ON o.order_id = oi.order_id""",
    "order_items.quantity not positive": """
        SELECT count(*) FROM order_items WHERE quantity IS NULL OR quantity <= 0""",
    "order_items.unit_price_paid negative or NULL": """
        SELECT count(*) FROM order_items WHERE unit_price_paid IS NULL OR unit_price_paid < 0""",
    "order_items.quantity_returned outside [0, quantity]": """
        SELECT count(*) FROM order_items
        WHERE quantity_returned IS NULL OR quantity_returned < 0 OR quantity_returned > quantity""",
    "returned items on non-returned orders": """
        SELECT count(*) FROM order_items AS oi
        JOIN orders AS o ON oi.order_id = o.order_id
        WHERE o.status <> 'returned' AND oi.quantity_returned > 0""",
    "returned orders with no returned units": """
        SELECT count(*) FROM (
            SELECT o.order_id
            FROM orders AS o
            JOIN order_items AS oi ON o.order_id = oi.order_id
            WHERE o.status = 'returned'
            GROUP BY 1
            HAVING sum(oi.quantity_returned) = 0
        )""",
}


class DataQualityError(RuntimeError):
    """Raised when one or more data quality checks find offending rows."""

    def __init__(self, failures: dict[str, int]) -> None:
        self.failures = failures
        details = "; ".join(f"{name}: {n} row(s)" for name, n in failures.items())
        super().__init__(f"{len(failures)} data quality check(s) failed -> {details}")


def build_checks() -> dict[str, str]:
    """Assemble key-integrity checks from the key maps, followed by the business rules."""
    checks: dict[str, str] = {}
    for table, pk in PRIMARY_KEYS.items():
        checks[f"{table}.{pk} NULL"] = f"SELECT count(*) FROM {table} WHERE {pk} IS NULL"
        checks[f"{table}.{pk} duplicated"] = f"SELECT count(*) - count(DISTINCT {pk}) FROM {table}"
    for child, fk, parent, ref in FOREIGN_KEYS:
        checks[f"{child}.{fk} NULL"] = f"SELECT count(*) FROM {child} WHERE {fk} IS NULL"
        checks[f"{child}.{fk} orphaned (no {parent})"] = (
            f"SELECT count(*) FROM {child} AS c ANTI JOIN {parent} AS p ON c.{fk} = p.{ref}"
        )
    checks.update(BUSINESS_RULES)
    return checks


def validate(con: duckdb.DuckDBPyConnection) -> None:
    """Run every check; raise DataQualityError listing all failures at once."""
    checks = build_checks()
    failures = {name: n for name, sql in checks.items() if (n := con.execute(sql).fetchone()[0])}
    if failures:
        raise DataQualityError(failures)
    log.info("Data quality: %d checks passed", len(checks))
