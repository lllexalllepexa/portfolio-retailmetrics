"""Smoke test: the dashboard renders against a tmp warehouse and reacts to filters."""

from __future__ import annotations

from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from retailmetrics import config
from retailmetrics.pipeline import build_warehouse_file
from tests.golden import GOLDEN, write_tables

APP = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")


@pytest.fixture
def app(tmp_path, monkeypatch) -> AppTest:
    warehouse = tmp_path / "warehouse.duckdb"
    build_warehouse_file(warehouse, data_dir=write_tables(tmp_path / "data", GOLDEN))
    monkeypatch.setattr(config, "WAREHOUSE_PATH", warehouse)
    st.cache_resource.clear()  # never reuse a connection to another test's warehouse
    st.cache_data.clear()
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    yield at
    st.cache_resource.clear()
    st.cache_data.clear()


def metric_value(at: AppTest, label: str) -> str:
    return next(m.value for m in at.metric if m.label == label)


def test_dashboard_renders_golden_kpis(app):
    assert not app.exception
    assert metric_value(app, "Net revenue") == "$126"
    assert metric_value(app, "Orders") == "3"
    assert metric_value(app, "AOV") == "$42.00"  # 126 / 3 paid orders, same definition as the marts


def test_country_filter_updates_kpis(app):
    app.sidebar.multiselect[0].set_value(["DE"]).run()
    assert not app.exception
    assert metric_value(app, "Net revenue") == "$50"
    assert metric_value(app, "Orders") == "1"
    assert metric_value(app, "AOV") == "$50.00"


def test_fully_refunded_order_is_excluded_from_aov(tmp_path, monkeypatch):
    tables = {table: list(rows) for table, rows in GOLDEN.items()}
    tables["order_items"][1] = (2, 101, 10, 3, "18.00", 3)  # order 101 fully refunded
    warehouse = tmp_path / "warehouse.duckdb"
    build_warehouse_file(warehouse, data_dir=write_tables(tmp_path / "data", tables))
    monkeypatch.setattr(config, "WAREHOUSE_PATH", warehouse)
    st.cache_resource.clear()
    st.cache_data.clear()
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert metric_value(at, "Orders") == "3"
    assert metric_value(at, "AOV") == "$45.00"  # (40 + 50) / 2 paid orders
    st.cache_resource.clear()
    st.cache_data.clear()


@pytest.mark.parametrize("show_ci", [False, True])
def test_cohort_table_leaves_censored_cells_empty(golden_marts, show_ci):
    from streamlit_app import cohort_tables

    rates, labels = cohort_tables(golden_marts["05_cohort_retention"], show_ci)
    assert labels.loc["2024-01 (n=1)", "Month 1"] == ("100.0% (21%–100%)" if show_ci else "100.0%")
    # March cohort: months 1-2 are after the last month of data -> NaN, rendered with placeholder=""
    assert rates.loc["2024-03 (n=1)", ["Month 1", "Month 2"]].isna().all()
    assert labels.loc["2024-03 (n=1)", ["Month 1", "Month 2"]].isna().all()


def test_usd_compact_format():
    from streamlit_app import usd

    assert [usd(126), usd(402_118.6), usd(1_448_429.39)] == ["$126", "$402.1K", "$1.45M"]
