"""
Automated test suite for retail metrics pipeline and data integrity.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.run_pipeline import main as run_pipeline_main

DATA_DIR = ROOT / "data"
OUTPUTS_DIR = ROOT / "outputs"
REPORTS_DIR = ROOT / "reports"

RAW_FILES = ["customers.csv", "orders.csv", "order_items.csv", "products.csv"]

EXPECTED_OUTPUTS = {
    "01_revenue_by_month.csv": ["order_month", "gmv_usd", "order_count"],
    "02_revenue_by_category.csv": ["category", "gmv_usd", "units_sold_net"],
    "03_country_orders_aov.csv": ["country", "orders", "gmv_usd", "aov_usd"],
    "04_top_products.csv": ["product_id", "name", "category", "gmv_usd"],
    "05_cohort_retention.csv": ["cohort_month", "cohort_customers", "month_offset", "retention_rate"],
}

EXPECTED_CHARTS = [
    "gmv_by_month.png",
    "gmv_by_category.png",
    "cohort_retention_heatmap.png",
]


def test_raw_data_exists_and_non_empty():
    """Check customers.csv, orders.csv, order_items.csv, products.csv in data/ exist and have > 0 rows."""
    for filename in RAW_FILES:
        file_path = DATA_DIR / filename
        assert file_path.exists(), f"Raw data file {filename} does not exist in {DATA_DIR}"
        df = pd.read_csv(file_path)
        assert len(df) > 0, f"Raw data file {filename} is empty"


def test_data_schemas_and_integrity():
    """Check required columns exist in each raw dataset, IDs are positive, prices and quantities are positive,
    and no invalid order statuses exist."""
    # 1. Customers
    cust_path = DATA_DIR / "customers.csv"
    assert cust_path.exists(), "customers.csv missing"
    df_cust = pd.read_csv(cust_path)
    for col in ["customer_id", "signup_date", "country"]:
        assert col in df_cust.columns, f"Missing column {col} in customers.csv"
    assert (df_cust["customer_id"] > 0).all(), "customer_id must be strictly positive"
    assert df_cust["customer_id"].is_unique, "customer_id must be unique"

    # 2. Products
    prod_path = DATA_DIR / "products.csv"
    assert prod_path.exists(), "products.csv missing"
    df_prod = pd.read_csv(prod_path)
    for col in ["product_id", "category", "name", "list_price"]:
        assert col in df_prod.columns, f"Missing column {col} in products.csv"
    assert (df_prod["product_id"] > 0).all(), "product_id must be strictly positive"
    assert (df_prod["list_price"] > 0).all(), "list_price must be strictly positive"
    assert df_prod["product_id"].is_unique, "product_id must be unique"

    # 3. Orders
    orders_path = DATA_DIR / "orders.csv"
    assert orders_path.exists(), "orders.csv missing"
    df_orders = pd.read_csv(orders_path)
    for col in ["order_id", "customer_id", "order_date", "status"]:
        assert col in df_orders.columns, f"Missing column {col} in orders.csv"
    assert (df_orders["order_id"] > 0).all(), "order_id must be strictly positive"
    assert (df_orders["customer_id"] > 0).all(), "customer_id must be strictly positive"
    assert df_orders["order_id"].is_unique, "order_id must be unique"

    valid_statuses = {"completed", "returned", "cancelled"}
    invalid_statuses = set(df_orders["status"].dropna().unique()) - valid_statuses
    assert not invalid_statuses, f"Found invalid order statuses: {invalid_statuses}"

    # 4. Order Items
    items_path = DATA_DIR / "order_items.csv"
    assert items_path.exists(), "order_items.csv missing"
    df_items = pd.read_csv(items_path)
    for col in ["order_line_id", "order_id", "product_id", "quantity", "unit_price_paid", "quantity_returned"]:
        assert col in df_items.columns, f"Missing column {col} in order_items.csv"
    assert (df_items["order_line_id"] > 0).all(), "order_line_id must be strictly positive"
    assert (df_items["order_id"] > 0).all(), "order_id must be strictly positive"
    assert (df_items["product_id"] > 0).all(), "product_id must be strictly positive"
    assert (df_items["quantity"] > 0).all(), "quantity must be strictly positive"
    assert (df_items["unit_price_paid"] > 0).all(), "unit_price_paid must be strictly positive"
    assert (df_items["quantity_returned"] >= 0).all(), "quantity_returned must be non-negative"
    assert (df_items["quantity_returned"] <= df_items["quantity"]).all(), "quantity_returned cannot exceed quantity"


def test_pipeline_outputs_validity():
    """Check all 5 outputs in outputs/ exist, have expected columns, gmv_usd > 0, and retention_rate is between 0.0 and 1.0."""
    for filename, expected_cols in EXPECTED_OUTPUTS.items():
        file_path = OUTPUTS_DIR / filename
        assert file_path.exists(), f"Output file {filename} does not exist in {OUTPUTS_DIR}"
        df = pd.read_csv(file_path)
        assert len(df) > 0, f"Output file {filename} is empty"
        for col in expected_cols:
            assert col in df.columns, f"Expected column '{col}' missing from {filename}"

        # Verify positive GMV where applicable
        if "gmv_usd" in df.columns:
            assert (df["gmv_usd"] > 0).all(), f"Found non-positive gmv_usd values in {filename}"

        # Verify retention rate range [0.0, 1.0]
        if "retention_rate" in df.columns:
            assert (df["retention_rate"] >= 0.0).all(), f"Found retention_rate < 0.0 in {filename}"
            assert (df["retention_rate"] <= 1.0).all(), f"Found retention_rate > 1.0 in {filename}"


def test_report_charts_exist():
    """Check reports/ contains gmv_by_month.png, gmv_by_category.png, and cohort_retention_heatmap.png,
    and all file sizes are > 10KB."""
    min_bytes = 10 * 1024  # 10 KB
    for chart_name in EXPECTED_CHARTS:
        chart_path = REPORTS_DIR / chart_name
        assert chart_path.exists(), f"Chart {chart_name} does not exist in {REPORTS_DIR}"
        size = chart_path.stat().st_size
        assert size > min_bytes, f"Chart {chart_name} size ({size} bytes) is not greater than 10KB ({min_bytes} bytes)"


def test_data_consistency():
    """Verify data consistency: no negative values, foreign key integrity, and valid order date ranges."""
    df_cust = pd.read_csv(DATA_DIR / "customers.csv")
    df_orders = pd.read_csv(DATA_DIR / "orders.csv")
    df_items = pd.read_csv(DATA_DIR / "order_items.csv")
    df_prod = pd.read_csv(DATA_DIR / "products.csv")

    # Foreign key integrity
    valid_customer_ids = set(df_cust["customer_id"])
    assert set(df_orders["customer_id"]).issubset(valid_customer_ids), "orders contains unknown customer_id"

    valid_order_ids = set(df_orders["order_id"])
    assert set(df_items["order_id"]).issubset(valid_order_ids), "order_items contains unknown order_id"

    valid_product_ids = set(df_prod["product_id"])
    assert set(df_items["product_id"]).issubset(valid_product_ids), "order_items contains unknown product_id"

    # Date consistency: order_date must not be before customer signup_date
    merged = df_orders.merge(df_cust, on="customer_id", how="inner")
    order_dates = pd.to_datetime(merged["order_date"])
    signup_dates = pd.to_datetime(merged["signup_date"])
    assert (order_dates >= signup_dates).all(), "order_date cannot precede customer signup_date"

    # No negative order monetary line values
    line_total = df_items["quantity"] * df_items["unit_price_paid"]
    assert (line_total > 0).all(), "Order item total value must be positive"


def test_pipeline_execution():
    """Test running run_pipeline.py cleanly and verify return code 0 and output files."""
    exit_code = run_pipeline_main()
    assert exit_code == 0, f"run_pipeline.main() returned non-zero exit code: {exit_code}"

    # Verify that outputs and charts exist post execution
    for filename in EXPECTED_OUTPUTS:
        assert (OUTPUTS_DIR / filename).exists(), f"Output file {filename} missing after pipeline run"

    for chart_name in EXPECTED_CHARTS:
        assert (REPORTS_DIR / chart_name).exists(), f"Chart {chart_name} missing after pipeline run"
