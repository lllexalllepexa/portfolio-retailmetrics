"""Smoke test: the dashboard renders from a tmp data dir and reacts to filters."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from retailmetrics import config
from tests.golden import GOLDEN, TableRows, write_tables

APP = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")


def run_app(tmp_path: Path, monkeypatch, tables: TableRows = GOLDEN) -> AppTest:
    monkeypatch.setattr(config, "DATA_DIR", write_tables(tmp_path / "data", tables))
    st.cache_resource.clear()  # never reuse a connection built from another test's data
    st.cache_data.clear()
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    return at


@pytest.fixture
def app(tmp_path, monkeypatch) -> AppTest:
    yield run_app(tmp_path, monkeypatch)
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
    at = run_app(tmp_path, monkeypatch, tables)
    assert metric_value(at, "Orders") == "3"
    assert metric_value(at, "AOV") == "$45.00"  # (40 + 50) / 2 paid orders
    st.cache_resource.clear()
    st.cache_data.clear()


def test_stale_warehouse_file_is_ignored(tmp_path, monkeypatch):
    # A warehouse.duckdb left by an earlier deploy (marts from older SQL) broke the live demo once.
    stale = tmp_path / "warehouse.duckdb"
    with duckdb.connect(str(stale)) as con:
        con.execute("CREATE TABLE mart_cohort_retention AS SELECT '2024-01' AS cohort_month, 1 AS cohort_customers")
    monkeypatch.setattr(config, "WAREHOUSE_PATH", stale)
    at = run_app(tmp_path, monkeypatch)
    assert not at.exception
    assert metric_value(at, "Net revenue") == "$126"
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
