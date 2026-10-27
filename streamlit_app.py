"""Interactive retail metrics dashboard backed by the DuckDB warehouse built by the pipeline."""

from __future__ import annotations

from datetime import date

import duckdb
import pandas as pd
import streamlit as st

from retailmetrics import config
from retailmetrics.pipeline import build_warehouse

FILTERS = """
    list_contains($countries, country)
    AND list_contains($categories, category)
    AND order_date BETWEEN $start AND $end
"""


@st.cache_resource
def get_connection() -> duckdb.DuckDBPyConnection:
    """Build the warehouse in memory from data/ once per process (about a second).

    A warehouse file left over from an earlier deploy would serve marts built by older SQL, so the
    dashboard never reads warehouse.duckdb; the pipeline CLI still writes it for ad-hoc queries.
    """
    con = duckdb.connect()
    build_warehouse(con, config.DATA_DIR, config.SQL_DIR)
    return con


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


def usd(value: float) -> str:
    """Compact dollar amount that fits a KPI tile: $126, $402.1K, $1.45M."""
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:,.2f}M"
    if abs(value) >= 1_000:
        return f"${value / 1_000:,.1f}K"
    return f"${value:,.0f}"


def render_kpis(selection: tuple) -> None:
    kpi = filtered(
        """
        WITH per_order AS (
            SELECT order_id, customer_id,
                   sum(net_revenue)      AS net_revenue,
                   sum(gross_revenue)    AS gross_revenue,
                   sum(returned_revenue) AS returned_revenue
            FROM fct_order_lines
            WHERE {filters}
            GROUP BY 1, 2
        )
        SELECT
            sum(net_revenue)                                      AS net_revenue,
            sum(gross_revenue)                                    AS gross_revenue,
            sum(returned_revenue) / nullif(sum(gross_revenue), 0) AS return_rate,
            count(*)                                              AS orders,
            count(*) FILTER (WHERE net_revenue > 0)               AS paid_orders,
            count(DISTINCT customer_id)                           AS customers
        FROM per_order
        """,
        *selection,
    ).to_dict("records")[0]  # records keep per-column dtypes; .iloc[0] would upcast ints to float
    if not kpi["orders"]:
        st.info("No qualifying orders match the current filters.")
        st.stop()
    aov = kpi["net_revenue"] / kpi["paid_orders"] if kpi["paid_orders"] else 0.0
    cols = st.columns(5)
    cols[0].metric("Net revenue", usd(kpi["net_revenue"]), help=f"${kpi['net_revenue']:,.2f} after returns.")
    cols[1].metric("Gross revenue", usd(kpi["gross_revenue"]), help=f"${kpi['gross_revenue']:,.2f} before returns.")
    cols[2].metric("Return rate", f"{kpi['return_rate']:.1%}", help="Returned revenue / gross revenue.")
    cols[3].metric("Orders", f"{kpi['orders']:,}", help="Completed + returned orders; cancelled orders are excluded.")
    cols[4].metric(
        "AOV",
        f"${aov:,.2f}",
        help="Net revenue / paid orders (fully refunded orders excluded), the same definition as the marts.",
    )
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
        st.bar_chart(by_category, x="category", y="Net revenue", horizontal=True, sort="-Net revenue", x_label="USD")


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
                "country": st.column_config.TextColumn("Country"),
                "orders": st.column_config.NumberColumn("Orders"),
                "paid_orders": st.column_config.NumberColumn("Paid orders"),
                "net_revenue": st.column_config.NumberColumn("Net revenue", format="dollar"),
                "aov": st.column_config.NumberColumn("AOV (paid orders)", format="dollar"),
            },
        )
    with right:
        st.subheader("Top 10 products")
        products = filtered(
            """
            SELECT product_id, product_name AS product, category,
                   sum(net_revenue) AS net_revenue,
                   sum(returned_revenue) / nullif(sum(gross_revenue), 0) AS return_rate
            FROM fct_order_lines WHERE {filters}
            GROUP BY 1, 2, 3 ORDER BY 4 DESC, 1 LIMIT 10
            """,
            *selection,
        )
        st.dataframe(
            products,
            hide_index=True,
            column_order=["product", "category", "net_revenue", "return_rate"],
            width="stretch",
            column_config={
                "product": st.column_config.TextColumn("Product"),
                "category": st.column_config.TextColumn("Category"),
                "net_revenue": st.column_config.NumberColumn("Net revenue", format="dollar"),
                "return_rate": st.column_config.NumberColumn("Return rate", format="percent"),
            },
        )


def cohort_tables(cohorts: pd.DataFrame, show_ci: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pivot the cohort mart into (numeric rates, display labels); censored cells stay NaN in both."""
    labels = [
        f"{rate:.1%} ({low:.0%}–{high:.0%})" if show_ci else f"{rate:.1%}"
        for rate, low, high in cohorts[["retention_rate", "retention_ci_low", "retention_ci_high"]].values
    ]
    sizes = cohorts.groupby("cohort_month")["cohort_customers"].first()
    tables = []
    for values in ("retention_rate", "label"):
        pivot = cohorts.assign(label=labels).pivot(index="cohort_month", columns="month_offset", values=values)
        pivot.columns = [f"Month {m}" for m in pivot.columns]
        pivot.index = [f"{c} (n={sizes[c]})" for c in pivot.index]
        tables.append(pivot)
    return tables[0], tables[1]


def render_cohorts() -> None:
    st.subheader("First-purchase cohort retention")
    show_ci = st.toggle("Show 95% confidence intervals", help="Wilson score interval for each cell.")
    rates, labels = cohort_tables(query("SELECT * FROM mart_cohort_retention"), show_ci)
    st.dataframe(
        labels.style.background_gradient(cmap="YlGnBu", vmin=0.0, vmax=1.0, gmap=rates, axis=None).highlight_null(
            props="background-color: transparent;"
        ),
        placeholder="",
        width="stretch",
    )
    st.caption(
        "Share of each first-purchase cohort with at least one qualifying order N months later. "
        "Blank cells are not yet observable (after the last month of data). "
        "See the README section 'Diagnosing Synthetic Artifacts' before reading trends into this table."
    )


def render_reading_notes() -> None:
    with st.expander("How to read these numbers (synthetic data)"):
        st.markdown(
            "- **Growth is volume, not value.** Net revenue per order stays flat while orders grow with the "
            "signed-up customer base; signups stop after April, so May–June plateau.\n"
            "- **Country AOV gaps are noise.** 95% confidence intervals overlap for every pair of countries.\n"
            "- **April–May cohorts look stickier** because the generator packs the same number of orders into "
            "fewer remaining months, not because of customer behaviour.\n\n"
            "Details and the queries behind each claim: README, section *Diagnosing Synthetic Artifacts*."
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
    render_reading_notes()
    render_trends(selection)
    render_breakdowns(selection)
    render_cohorts()


if __name__ == "__main__":
    main()
