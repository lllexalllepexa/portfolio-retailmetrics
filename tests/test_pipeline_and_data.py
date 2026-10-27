"""End-to-end pipeline, generator and committed-artifact checks. All writes go to tmp dirs."""

from __future__ import annotations

import random
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from retailmetrics import config
from retailmetrics.io import SCHEMAS, load_tables
from retailmetrics.models import DIAGNOSTIC_MODELS, MART_MODELS
from retailmetrics.pipeline import main as run_pipeline
from retailmetrics.quality import validate
from scripts.generate_data import generate, returned_units

CHARTS = ["revenue_by_month.png", "revenue_by_category.png", "cohort_retention_heatmap.png"]


@pytest.fixture(scope="module")
def pipeline_run(tmp_path_factory) -> dict[str, Path]:
    """Generate seed-42 data and run the full pipeline once, entirely inside a tmp dir."""
    root = tmp_path_factory.mktemp("run")
    dirs = {name: root / name for name in ("data", "outputs", "reports")}
    generate(dirs["data"], seed=42)
    dirs["warehouse"] = root / "warehouse.duckdb"
    exit_code = run_pipeline(
        [
            f"--data-dir={dirs['data']}",
            f"--outputs-dir={dirs['outputs']}",
            f"--reports-dir={dirs['reports']}",
            f"--warehouse={dirs['warehouse']}",
        ]
    )
    assert exit_code == 0
    return dirs


def read_output(run: dict[str, Path], model: str) -> pd.DataFrame:
    return pd.read_csv(run["outputs"] / f"{model}.csv")


# --- generator -------------------------------------------------------------------------------


@pytest.mark.parametrize("qty", [1, 2, 3])
def test_returned_units_bounds(qty):
    rng = random.Random(0)
    draws = [returned_units("returned", qty, rng) for _ in range(500)]
    assert min(draws) >= 1 and max(draws) == qty
    assert returned_units("completed", qty, rng) == 0
    assert returned_units("cancelled", qty, rng) == 0


def test_generator_is_deterministic(tmp_path):
    generate(tmp_path / "a", seed=7)
    generate(tmp_path / "b", seed=7)
    for table in SCHEMAS:
        assert (tmp_path / "a" / f"{table}.csv").read_bytes() == (tmp_path / "b" / f"{table}.csv").read_bytes()


# --- end-to-end ------------------------------------------------------------------------------


def test_pipeline_writes_all_marts_and_charts(pipeline_run):
    for model in MART_MODELS + DIAGNOSTIC_MODELS:
        assert not read_output(pipeline_run, model).empty, model
    for chart in CHARTS:
        assert (pipeline_run["reports"] / chart).stat().st_size > 0, chart
    assert pipeline_run["warehouse"].exists()


def test_net_revenue_reconciles_across_marts(pipeline_run):
    totals = {
        model: read_output(pipeline_run, model)["net_revenue_usd"].sum()
        for model in ("01_revenue_by_month", "02_revenue_by_category", "03_country_orders_aov")
    }
    assert len({round(t, 2) for t in totals.values()}) == 1, totals


def test_cohort_invariants_on_full_dataset(pipeline_run):
    df = read_output(pipeline_run, "05_cohort_retention")
    assert (df.loc[df.month_offset == 0, "retention_rate"] == 1.0).all()
    assert df["retention_rate"].between(0.0, 1.0).all()
    assert (df["active_customers"] <= df["cohort_customers"]).all()
    assert (df["retention_ci_low"] <= df["retention_rate"]).all()
    assert (df["retention_rate"] <= df["retention_ci_high"]).all()


def test_diagnostics_reconcile_with_marts(pipeline_run):
    aov = read_output(pipeline_run, "03_country_orders_aov").set_index("country")
    aov_ci = read_output(pipeline_run, "diagnostics/country_aov_ci").set_index("country")
    pd.testing.assert_series_equal(aov_ci["aov_usd"], aov.loc[aov_ci.index, "aov_usd"], check_names=False)
    assert (aov_ci["paid_orders"] == aov.loc[aov_ci.index, "paid_orders"]).all()

    monthly = read_output(pipeline_run, "01_revenue_by_month")
    activity = read_output(pipeline_run, "diagnostics/monthly_activity")
    assert activity["orders"].tolist() == monthly["order_count"].tolist()


def test_warehouse_exposes_staging_and_marts(pipeline_run):
    with duckdb.connect(str(pipeline_run["warehouse"]), read_only=True) as con:
        tables = {row[0] for row in con.execute("SELECT table_name FROM information_schema.tables").fetchall()}
    assert {"fct_order_lines", "mart_revenue_by_month", "mart_cohort_retention"} <= tables


# --- committed artifacts (read-only) ---------------------------------------------------------


def test_committed_data_passes_quality_gates():
    with duckdb.connect() as con:
        load_tables(con, config.DATA_DIR)
        validate(con)


@pytest.mark.parametrize("table", list(SCHEMAS))
def test_committed_data_matches_generator(pipeline_run, table):
    committed = pd.read_csv(config.DATA_DIR / f"{table}.csv")
    regenerated = pd.read_csv(pipeline_run["data"] / f"{table}.csv")
    pd.testing.assert_frame_equal(committed, regenerated)


@pytest.mark.parametrize("model", MART_MODELS + DIAGNOSTIC_MODELS)
def test_committed_outputs_match_pipeline(pipeline_run, model):
    committed = pd.read_csv(config.OUTPUTS_DIR / f"{model}.csv")
    pd.testing.assert_frame_equal(committed, read_output(pipeline_run, model))
