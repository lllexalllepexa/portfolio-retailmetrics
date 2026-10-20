"""Static chart rendering for the README and reports/ folder."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: CI, containers and Windows without Tk

import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mtick  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402

USD = mtick.StrMethodFormatter("${x:,.0f}")


def render_revenue_by_month(df: pd.DataFrame, path: Path, dpi: int = 150) -> Path:
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(df["order_month"], df["gross_revenue_usd"], color="#bcccdc", label="Gross revenue")
    ax.bar(df["order_month"], df["net_revenue_usd"], color="#2c5282", label="Net revenue (after returns)")
    ax.set_title("Revenue by month (USD)")
    ax.set_xlabel("Order month")
    ax.yaxis.set_major_formatter(USD)
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    return _save(fig, path, dpi)


def render_revenue_by_category(df: pd.DataFrame, path: Path, dpi: int = 150) -> Path:
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.barh(df["category"], df["net_revenue_usd"], color="#276749")
    ax.invert_yaxis()
    ax.set_title("Net revenue by category (USD)")
    ax.xaxis.set_major_formatter(USD)
    ax.spines[["top", "right"]].set_visible(False)
    return _save(fig, path, dpi)


def render_cohort_heatmap(df: pd.DataFrame, path: Path, dpi: int = 150, palette: str = "YlGnBu") -> Path:
    """Heatmap of first-purchase cohort retention. Right-censored cells are left blank."""
    required = {"cohort_month", "cohort_customers", "month_offset", "retention_rate"}
    if missing := required - set(df.columns):
        raise ValueError(f"Cohort data is missing required columns: {sorted(missing)}")

    pivot = df.pivot(index="cohort_month", columns="month_offset", values="retention_rate")
    sizes = df.groupby("cohort_month")["cohort_customers"].first()

    with sns.axes_style("white"):
        fig, ax = plt.subplots(figsize=(9.5, 5.5))
        sns.heatmap(
            pivot,
            annot=True,
            fmt=".1%",
            cmap=palette,
            vmin=0.0,
            vmax=1.0,
            linewidths=1.5,
            linecolor="white",
            cbar_kws={"label": "Retention rate", "format": mtick.PercentFormatter(1.0)},
            yticklabels=[f"{c} (n={sizes[c]:,})" for c in pivot.index],
            xticklabels=[f"Month {m}" for m in pivot.columns],
            ax=ax,
        )
    fig.suptitle("First-purchase cohort retention", fontsize=15, fontweight="bold")
    ax.set_title(
        "Share of each cohort placing >= 1 qualifying order N months after the first; blank = not yet observable",
        fontsize=9.5,
        color="#4a5568",
    )
    ax.set_xlabel("Months since first purchase")
    ax.set_ylabel("Cohort (first-purchase month)")
    ax.tick_params(axis="y", rotation=0)
    return _save(fig, path, dpi)


def _save(fig: plt.Figure, path: Path, dpi: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return path
