"""Build the staging layer and materialize the analytical marts in dependency order."""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb
import pandas as pd

from retailmetrics.config import SQL_DIR

log = logging.getLogger(__name__)

STAGING_MODELS: tuple[str, ...] = ("staging/fct_order_lines",)

MART_MODELS: tuple[str, ...] = (
    "01_revenue_by_month",
    "02_revenue_by_category",
    "03_country_orders_aov",
    "04_top_products",
    "05_cohort_retention",
)


def mart_table_name(model: str) -> str:
    """'01_revenue_by_month' -> 'mart_revenue_by_month' (identifiers cannot start with a digit)."""
    return "mart_" + model.split("_", 1)[1]


def read_model_sql(model: str, sql_dir: Path = SQL_DIR) -> str:
    return (sql_dir / f"{model}.sql").read_text(encoding="utf-8").strip().rstrip(";")


def build_staging(con: duckdb.DuckDBPyConnection, sql_dir: Path = SQL_DIR) -> None:
    for model in STAGING_MODELS:
        con.execute(read_model_sql(model, sql_dir))
        log.info("Built staging model %s", model)


def build_marts(con: duckdb.DuckDBPyConnection, sql_dir: Path = SQL_DIR) -> dict[str, pd.DataFrame]:
    """Materialize each mart as a table and return its contents keyed by model name."""
    results: dict[str, pd.DataFrame] = {}
    for model in MART_MODELS:
        table = mart_table_name(model)
        con.execute(f"CREATE OR REPLACE TABLE {table} AS\n{read_model_sql(model, sql_dir)}")
        results[model] = con.execute(f"SELECT * FROM {table}").df()
        log.info("Built mart %-24s %4d rows", table, len(results[model]))
    return results


def run_models(con: duckdb.DuckDBPyConnection, sql_dir: Path = SQL_DIR) -> dict[str, pd.DataFrame]:
    """Build staging then marts on a connection whose raw tables are already loaded."""
    build_staging(con, sql_dir)
    return build_marts(con, sql_dir)
