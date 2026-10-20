"""Schema-enforced loading of raw CSVs into DuckDB."""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb

log = logging.getLogger(__name__)

# Column order matches the CSV headers; types are enforced instead of inferred.
SCHEMAS: dict[str, dict[str, str]] = {
    "customers": {
        "customer_id": "INTEGER",
        "signup_date": "DATE",
        "country": "VARCHAR",
    },
    "products": {
        "product_id": "INTEGER",
        "category": "VARCHAR",
        "name": "VARCHAR",
        "list_price": "DECIMAL(10, 2)",
    },
    "orders": {
        "order_id": "INTEGER",
        "customer_id": "INTEGER",
        "order_date": "DATE",
        "status": "VARCHAR",
    },
    "order_items": {
        "order_line_id": "INTEGER",
        "order_id": "INTEGER",
        "product_id": "INTEGER",
        "quantity": "INTEGER",
        "unit_price_paid": "DECIMAL(10, 2)",
        "quantity_returned": "INTEGER",
    },
}


class SchemaError(ValueError):
    """Raised when a raw file's header does not match its declared schema."""


def load_tables(con: duckdb.DuckDBPyConnection, data_dir: Path) -> None:
    """Load every table in SCHEMAS from ``data_dir/<table>.csv`` with explicit column types."""
    for table, columns in SCHEMAS.items():
        path = data_dir / f"{table}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Missing {path}. Run: python scripts/generate_data.py")

        try:
            rel = con.read_csv(path.as_posix(), header=True, dtype=columns)
        except duckdb.BinderException as exc:  # a typed column is missing from the header
            raise SchemaError(f"{path.name}: {exc}") from exc
        if rel.columns != list(columns):
            raise SchemaError(f"{path.name}: expected columns {list(columns)}, found {rel.columns}")

        rel.create(table)
        n_rows = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        log.info("Loaded %-11s %6d rows", table, n_rows)
