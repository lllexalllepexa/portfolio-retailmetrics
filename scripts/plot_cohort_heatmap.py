"""Generate publication-quality cohort retention heatmap visualization.

Reads outputs/05_cohort_retention.csv (or generates it via DuckDB if missing),
pivots the retention rates across acquisition cohorts and monthly offsets,
and renders a polished Seaborn heatmap saved to reports/cohort_retention_heatmap.png.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Union

import duckdb
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd
import seaborn as sns

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SQL = ROOT / "sql"
OUT = ROOT / "outputs"
REP = ROOT / "reports"


def load_cohort_data(csv_path: Union[Path, str, None] = None) -> pd.DataFrame:
    """Load cohort retention data from CSV or compute it via DuckDB if not present."""
    path = Path(csv_path) if csv_path else OUT / "05_cohort_retention.csv"

    if path.exists():
        return pd.read_csv(path)

    # If outputs CSV does not exist, compute on-the-fly using DuckDB
    sql_path = SQL / "05_cohort_retention.sql"
    if not sql_path.exists():
        raise FileNotFoundError(f"Cohort retention SQL query not found at {sql_path}")

    con = duckdb.connect(database=":memory:")
    for table, fname in [
        ("customers", "customers.csv"),
        ("orders", "orders.csv"),
        ("order_items", "order_items.csv"),
        ("products", "products.csv"),
    ]:
        tbl_path = DATA / fname
        if not tbl_path.exists():
            raise FileNotFoundError(
                f"Missing dataset {tbl_path}. Please run: python scripts/generate_data.py"
            )
        posix_path = tbl_path.resolve().as_posix().replace("'", "''")
        con.execute(
            f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_csv_auto('{posix_path}');"
        )

    df = con.execute(sql_path.read_text(encoding="utf-8")).df()
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return df


def render_cohort_heatmap(
    data: Union[pd.DataFrame, Path, str, None] = None,
    output_path: Union[Path, str, None] = None,
    palette: str = "YlGnBu",
    dpi: int = 150,
) -> Path:
    """Render publication-quality cohort retention heatmap and save to disk.

    Parameters
    ----------
    data : pd.DataFrame | Path | str | None
        Cohort retention DataFrame or path to CSV. If None, loads from outputs.
    output_path : Path | str | None
        Target path for saved figure. Defaults to reports/cohort_retention_heatmap.png.
    palette : str
        Seaborn color palette name (e.g. 'YlGnBu', 'Blues').
    dpi : int
        Image resolution in dots per inch (default: 150).

    Returns
    -------
    Path
        Absolute or resolved path to the saved image file.
    """
    if isinstance(data, pd.DataFrame):
        df = data.copy()
    else:
        df = load_cohort_data(data)

    required_cols = {"cohort_month", "cohort_customers", "month_offset", "retention_rate"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Dataframe is missing required columns: {missing}")

    # Map cohort sizes for y-tick labels
    cohort_sizes = df.groupby("cohort_month")["cohort_customers"].first()

    # Pivot data: rows = cohort_month, columns = month_offset, values = retention_rate
    pivot_df = df.pivot(index="cohort_month", columns="month_offset", values="retention_rate")

    # Format axis tick labels
    y_labels = [f"{cohort} (n={cohort_sizes.get(cohort, 0):,})" for cohort in pivot_df.index]
    x_labels = [f"Month {col}" for col in pivot_df.columns]

    # Dynamically determine colorbar ceiling (max rate rounded up to nearest 10%, min 50%)
    max_rate = float(pivot_df.max().max())
    vmax = min(1.0, max(0.5, (int(max_rate * 10) + 1) / 10.0))

    # Setup plot aesthetic
    sns.set_theme(style="white")
    fig, ax = plt.subplots(figsize=(9.5, 5.5))

    sns.heatmap(
        pivot_df,
        annot=True,
        fmt=".1%",
        cmap=palette,
        vmin=0.0,
        vmax=vmax,
        linewidths=1.5,
        linecolor="white",
        cbar_kws={
            "label": "Retention Rate",
            "format": mtick.PercentFormatter(1.0),
            "pad": 0.03,
        },
        yticklabels=y_labels,
        xticklabels=x_labels,
        ax=ax,
    )

    # Professional titles and labels
    ax.set_title("Customer Cohort Retention Analysis\n", fontsize=15, fontweight="bold", pad=12)
    ax.text(
        0.5,
        1.02,
        "Percentage of registered customers placing repeat qualifying orders over time",
        fontsize=10.5,
        color="#4a5568",
        ha="center",
        transform=ax.transAxes,
    )
    ax.set_xlabel("Months Since Registration", fontsize=11.5, fontweight="semibold", labelpad=12)
    ax.set_ylabel("Acquisition Cohort", fontsize=11.5, fontweight="semibold", labelpad=12)

    ax.tick_params(axis="y", rotation=0, labelsize=10)
    ax.tick_params(axis="x", labelsize=10)

    # Save figure
    target_file = Path(output_path) if output_path else REP / "cohort_retention_heatmap.png"
    target_file.parent.mkdir(parents=True, exist_ok=True)

    fig.tight_layout()
    fig.savefig(target_file, dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    return target_file


def main() -> int:
    out_file = render_cohort_heatmap()
    print(f"Cohort retention heatmap successfully generated -> {out_file} ({out_file.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
