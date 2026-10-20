"""Interactive retail metrics dashboard backed by the DuckDB warehouse built by the pipeline."""

from __future__ import annotations

from datetime import date

import duckdb
import pandas as pd
import streamlit as st

from retailmetrics import config
from retailmetrics.pipeline import build_warehouse_file

FILTERS = """
    list_contains($countries, country)
    AND list_contains($categories, category)
    AND order_date BETWEEN $start AND $end
"""


@st.cache_resource
def get_connection() -> duckdb.DuckDBPyConnection:
    """Open the warehouse read-only, building it from data/ first if it does not exist yet."""
    if not config.WAREHOUSE_PATH.exists():
        build_warehouse_file()
    return duckdb.connect(str(config.WAREHOUSE_PATH), read_only=True)


def query(sql: str, params: dict | None = None) -> pd.DataFrame:
    # A cursor per query: one shared DuckDB connection is not safe across Streamlit threads.
    return get_connection().cursor().execute(sql, params or {}).df()


@st.cache_data
def filter_options() -> tuple[list[str], list[str], date, date]:
    dims = query(
        """
        SELECT
            (SELECT list(DISTINCT country ORDER BY country) FROM fct_order_lines)   AS countries,
            (SELECT list(DISTINCT category ORDER BY category) FROM fct_order_lines) AS categories,
            (SELECT min(order_date) FROM fct_order_lines)                          AS first_day,
            (SELECT max(order_date) FROM fct_order_lines)                          AS last_day
        """
    ).iloc[0]
    return list(dims.countries), list(dims.categories), dims.first_day.date(), dims.last_day.date()


@st.cache_data
def filtered(sql: str, countries: tuple[str, ...], categories: tuple[str, ...], start: date, end: date) -> pd.DataFrame:
    params = {"countries": list(countries), "categories": list(categories), "start": start, "end": end}
    return query(sql.format(filters=FILTERS), params)


def render_sidebar() -> tuple[tuple[str, ...], tuple[str, ...], date, date]:
    countries, categories, first_day, last_day = filter_options()
    st.sidebar.header("Filters")
    sel_countries = st.sidebar.multiselect("Country", countries, default=countries)
    sel_categories = st.sidebar.multiselect("Category", categories, default=categories)
    picked = st.sidebar.date_input("Order date", (first_day, last_day), min_value=first_day, max_value=last_day)
    start, end = picked if isinstance(picked, tuple) and len(picked) == 2 else (first_day, last_day)
    st.sidebar.caption("Filters apply to every section except cohort retention (whole-customer metric).")
    return tuple(sel_countries), tuple(sel_categories), start, end


def render_kpis(selection: tuple) -> None:
    kpi = filtered(
        """
        SELECT
            sum(net_revenue)                                   AS net_revenue,
            sum(gross_revenue)                                 AS gross_revenue,
            sum(returned_revenue) / nullif(sum(gross_revenue), 0) AS return_rate,
            count(DISTINCT order_id)                           AS orders,
            count(DISTINCT customer_id)                        AS customers
        FROM fct_order_lines
        WHERE {filters}
        """,
        *selection,
    ).to_dict("records")[0]  # records keep per-column dtypes; .iloc[0] would upcast ints to float
    if not kpi["orders"]:
        st.info("No qualifying orders match the current filters.")
        st.stop()
    aov = kpi["net_revenue"] / kpi["orders"]
    cols = st.columns(5)
    cols[0].metric("Net revenue", f"${kpi['net_revenue']:,.0f}")
    cols[1].metric("Gross revenue", f"${kpi['gross_revenue']:,.0f}")
    cols[2].metric("Return rate", f"{kpi['return_rate']:.1%}")
    cols[3].metric("Orders", f"{kpi['orders']:,}", help="Completed + returned orders; cancelled orders are excluded.")
    cols[4].metric("Net revenue per order", f"${aov:,.2f}", help="Net revenue / orders in the current selection.")
    st.caption(f"{kpi['customers']:,} purchasing customers in selection")


def render_trends(selection: tuple) -> None:
    left, right = st.columns(2)
    with left:
        st.subheader("Revenue by month")
        monthly = filtered(
            """
            SELECT strftime(order_date, '%Y-%m') AS month,
                   sum(gross_revenue) AS "Gross revenue",
                   sum(net_revenue)   AS "Net revenue"
            FROM fct_order_lines WHERE {filters}
            GROUP BY 1 ORDER BY 1
            """,
            *selection,
        )
        st.bar_chart(monthly, x="month", y=["Gross revenue", "Net revenue"], stack=False, y_label="USD")
    with right:
        st.subheader("Net revenue by category")
        by_category = filtered(
            """
            SELECT category, sum(net_revenue) AS "Net revenue"
            FROM fct_order_lines WHERE {filters}
            GROUP BY 1 ORDER BY 2 DESC
            """,
            *selection,
        )
        st.bar_chart(by_category, x="category", y="Net revenue", horizontal=True, x_label="USD")


def render_breakdowns(selection: tuple) -> None:
    left, right = st.columns(2)
    with left:
        st.subheader("Country mix")
        countries = filtered(
            """
            WITH per_order AS (
                SELECT order_id, country, sum(net_revenue) AS net_revenue
                FROM fct_order_lines WHERE {filters}
                GROUP BY 1, 2
            )
            SELECT country,
                   count(*)                                AS orders,
                   count(*) FILTER (WHERE net_revenue > 0) AS paid_orders,
                   sum(net_revenue)                        AS net_revenue,
                   sum(net_revenue) / nullif(count(*) FILTER (WHERE net_revenue > 0), 0) AS aov
            FROM per_order GROUP BY 1 ORDER BY net_revenue DESC
            """,
            *selection,
        )
        st.dataframe(
            countries,
            hide_index=True,
            width="stretch",
            column_config={
                "net_revenue": st.column_config.NumberColumn("Net revenue", format="dollar"),
                "aov": st.column_config.NumberColumn("AOV (paid orders)", format="dollar"),
            },
        )
    with right:
        st.subheader("Top 10 products")
        products = filtered(
            """
            SELECT product_name AS product, category,
                   sum(net_revenue) AS net_revenue,
                   sum(returned_revenue) / nullif(sum(gross_revenue), 0) AS return_rate
            FROM fct_order_lines WHERE {filters}
            GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 10
            """,
            *selection,
        )
        st.dataframe(
            products,
            hide_index=True,
            width="stretch",
            column_config={
                "net_revenue": st.column_config.NumberColumn("Net revenue", format="dollar"),
                "return_rate": st.column_config.NumberColumn("Return rate", format="percent"),
            },
        )


def render_cohorts() -> None:
    st.subheader("First-purchase cohort retention")
    cohorts = query("SELECT * FROM mart_cohort_retention")
    pivot = cohorts.pivot(index="cohort_month", columns="month_offset", values="retention_rate")
    pivot.columns = [f"Month {m}" for m in pivot.columns]
    sizes = cohorts.groupby("cohort_month")["cohort_customers"].first()
    pivot.index = [f"{c} (n={sizes[c]})" for c in pivot.index]
    st.dataframe(
        pivot.style.format("{:.1%}", na_rep="").background_gradient(cmap="YlGnBu", vmin=0.0, vmax=1.0),
        width="stretch",
    )
    st.caption(
        "Share of each first-purchase cohort with at least one qualifying order N months later. "
        "Blank cells are not yet observable (after the last month of data). "
        "See the README section 'Diagnosing Synthetic Artifacts' before reading trends into this table."
    )


def main() -> None:
    st.set_page_config(page_title="Retail Metrics", layout="wide")
    st.title("Retail Metrics & Cohort Analytics")
    st.caption("Synthetic B2C e-commerce data · DuckDB staging + marts · all figures in USD")

    try:
        get_connection()
    except FileNotFoundError as exc:
        st.error(f"{exc}. Generate the raw data first: `python scripts/generate_data.py`.")
        st.stop()

    selection = render_sidebar()
    if not selection[0] or not selection[1]:
        st.info("Select at least one country and one category.")
        st.stop()

    render_kpis(selection)
    render_trends(selection)
    render_breakdowns(selection)
    render_cohorts()


if __name__ == "__main__":
    main()
