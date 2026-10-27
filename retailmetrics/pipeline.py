"""Pipeline entry point: load -> validate -> staging -> marts -> CSV exports + charts.

Run: python -m retailmetrics.pipeline
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import duckdb
import pandas as pd

from retailmetrics import charts, config
from retailmetrics.io import load_tables
from retailmetrics.models import run_models
from retailmetrics.quality import validate

log = logging.getLogger(__name__)


def build_warehouse(
    con: duckdb.DuckDBPyConnection,
    data_dir: Path = config.DATA_DIR,
    sql_dir: Path = config.SQL_DIR,
) -> dict[str, pd.DataFrame]:
    """Load raw tables, enforce data quality, then build staging and marts on ``con``."""
    load_tables(con, data_dir)
    validate(con)
    return run_models(con, sql_dir)


def build_warehouse_file(
    path: Path = config.WAREHOUSE_PATH,
    data_dir: Path = config.DATA_DIR,
    sql_dir: Path = config.SQL_DIR,
) -> dict[str, pd.DataFrame]:
    """Rebuild the persistent DuckDB file from scratch."""
    path.parent.mkdir(parents=True, exist_ok=True)
    for stale in (path, path.with_name(path.name + ".wal")):
        stale.unlink(missing_ok=True)
    with duckdb.connect(str(path)) as con:
        return build_warehouse(con, data_dir, sql_dir)


def export_outputs(results: dict[str, pd.DataFrame], out_dir: Path) -> None:
    for model, df in results.items():
        path = out_dir / f"{model}.csv"  # diagnostics land in out_dir/diagnostics/
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False, lineterminator="\n")
    log.info("Wrote %d CSVs -> %s", len(results), out_dir)


def render_reports(results: dict[str, pd.DataFrame], reports_dir: Path) -> None:
    charts.render_revenue_by_month(results["01_revenue_by_month"], reports_dir / "revenue_by_month.png")
    charts.render_revenue_by_category(results["02_revenue_by_category"], reports_dir / "revenue_by_category.png")
    charts.render_cohort_heatmap(results["05_cohort_retention"], reports_dir / "cohort_retention_heatmap.png")
    log.info("Wrote charts -> %s", reports_dir)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=Path, default=config.DATA_DIR)
    parser.add_argument("--sql-dir", type=Path, default=config.SQL_DIR)
    parser.add_argument("--outputs-dir", type=Path, default=config.OUTPUTS_DIR)
    parser.add_argument("--reports-dir", type=Path, default=config.REPORTS_DIR)
    parser.add_argument("--warehouse", type=Path, default=config.WAREHOUSE_PATH)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    args = parse_args(argv)
    results = build_warehouse_file(args.warehouse, args.data_dir, args.sql_dir)
    export_outputs(results, args.outputs_dir)
    render_reports(results, args.reports_dir)
    log.info("Warehouse ready -> %s", args.warehouse)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
