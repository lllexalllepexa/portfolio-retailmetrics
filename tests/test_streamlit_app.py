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


def test_country_filter_updates_kpis(app):
    app.sidebar.multiselect[0].set_value(["DE"]).run()
    assert not app.exception
    assert metric_value(app, "Net revenue") == "$50"
    assert metric_value(app, "Orders") == "1"
