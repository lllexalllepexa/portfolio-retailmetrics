"""Shared fixtures. Every test writes only under pytest's tmp_path, never into the repository."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from retailmetrics.io import load_tables
from retailmetrics.models import run_models
from retailmetrics.quality import validate
from tests.golden import GOLDEN, TableRows, write_tables


@pytest.fixture
def golden_tables() -> TableRows:
    """A fresh, mutable copy of the golden rows for tests that inject defects."""
    return {table: list(rows) for table, rows in GOLDEN.items()}


@pytest.fixture
def load_fixture(tmp_path: Path) -> Iterator[Callable[[TableRows], duckdb.DuckDBPyConnection]]:
    """Write tables to tmp_path as CSV and load them through the real schema-enforced loader."""
    connections: list[duckdb.DuckDBPyConnection] = []

    def _load(tables: TableRows) -> duckdb.DuckDBPyConnection:
        con = duckdb.connect()
        connections.append(con)
        load_tables(con, write_tables(tmp_path / "data", tables))
        return con

    yield _load
    for con in connections:
        con.close()


@pytest.fixture
def golden_marts(load_fixture, golden_tables) -> dict[str, pd.DataFrame]:
    con = load_fixture(golden_tables)
    validate(con)
    return run_models(con)
