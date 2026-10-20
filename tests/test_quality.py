"""Data quality gates and schema enforcement reject bad inputs."""

from __future__ import annotations

import duckdb
import pytest

from retailmetrics.io import SchemaError, load_tables
from retailmetrics.quality import DataQualityError, validate
from tests.golden import GOLDEN, write_tables


def test_golden_fixture_passes(load_fixture, golden_tables):
    validate(load_fixture(golden_tables))


@pytest.mark.parametrize(
    ("table", "index", "row", "expected_check"),
    [
        ("order_items", 0, (1, 999, 10, 2, "20.00", 0), "order_items.order_id orphaned (no orders)"),
        ("order_items", 0, (1, 100, 99, 2, "20.00", 0), "order_items.product_id orphaned (no products)"),
        ("order_items", 1, (2, 101, 10, 3, "18.00", 4), "order_items.quantity_returned outside [0, quantity]"),
        ("order_items", 0, (1, 100, 10, 2, "20.00", 1), "returned items on non-returned orders"),
        ("order_items", 1, (2, 101, 10, 3, "18.00", 0), "returned orders with no returned units"),
        ("orders", 0, (100, 1, "2024-01-01", "completed"), "orders.order_date before customers.signup_date"),
        ("orders", 0, (100, 1, "2024-01-10", "shipped"), "orders.status outside allowed values"),
        ("orders", 0, (100, "", "2024-01-10", "completed"), "orders.customer_id NULL"),
        ("customers", 1, (1, "2024-01-20", "DE"), "customers.customer_id duplicated"),
        ("products", 0, ("", "Books", "Book A", "20.00"), "products.product_id NULL"),
    ],
)
def test_defect_raises_data_quality_error(load_fixture, golden_tables, table, index, row, expected_check):
    golden_tables[table][index] = row
    con = load_fixture(golden_tables)
    with pytest.raises(DataQualityError) as excinfo:
        validate(con)
    assert expected_check in excinfo.value.failures


def test_all_failures_reported_together(load_fixture, golden_tables):
    golden_tables["orders"][0] = (100, 1, "2024-01-01", "shipped")
    with pytest.raises(DataQualityError) as excinfo:
        validate(load_fixture(golden_tables))
    assert len(excinfo.value.failures) >= 2


def test_wrong_header_rejected(tmp_path):
    data_dir = write_tables(tmp_path, GOLDEN)
    path = data_dir / "orders.csv"
    path.write_text(path.read_text(encoding="utf-8").replace("order_date", "created_at", 1), encoding="utf-8")
    with duckdb.connect() as con, pytest.raises(SchemaError):
        load_tables(con, data_dir)


def test_missing_file_rejected(tmp_path):
    with duckdb.connect() as con, pytest.raises(FileNotFoundError):
        load_tables(con, tmp_path)
