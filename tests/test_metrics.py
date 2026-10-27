"""Metric correctness on the hand-computed golden fixture (see conftest.GOLDEN)."""

from __future__ import annotations

import pandas as pd
import pytest


def records(df: pd.DataFrame, columns: list[str]) -> list[dict]:
    return df[columns].to_dict("records")


def test_monthly_revenue_nets_returns_and_excludes_cancelled(golden_marts):
    df = golden_marts["01_revenue_by_month"]
    assert records(df, ["order_month", "gross_revenue_usd", "net_revenue_usd", "order_count"]) == [
        # Jan: 2 x 20 from order 100; cancelled order 102 (50.00) is excluded
        {"order_month": "2024-01", "gross_revenue_usd": 40.0, "net_revenue_usd": 40.0, "order_count": 1},
        # Feb: gross 3 x 18 = 54, net (3 - 1) x 18 = 36
        {"order_month": "2024-02", "gross_revenue_usd": 54.0, "net_revenue_usd": 36.0, "order_count": 1},
        {"order_month": "2024-03", "gross_revenue_usd": 50.0, "net_revenue_usd": 50.0, "order_count": 1},
    ]
    assert df["return_rate"].tolist() == pytest.approx([0.0, 0.3333, 0.0])


def test_category_units_are_integers_not_floats(golden_marts):
    df = golden_marts["02_revenue_by_category"]
    assert pd.api.types.is_integer_dtype(df["units_sold_net"])
    assert records(df, ["category", "net_revenue_usd", "units_sold_net"]) == [
        {"category": "Books", "net_revenue_usd": 76.0, "units_sold_net": 4},  # 2 + (3 - 1)
        {"category": "Home", "net_revenue_usd": 50.0, "units_sold_net": 1},
    ]
    assert df.loc[df.category == "Books", "return_rate"].item() == pytest.approx(round(18 / 94, 4))


def test_country_aov_uses_net_revenue_over_paid_orders(golden_marts):
    df = golden_marts["03_country_orders_aov"]
    assert records(df, ["country", "orders", "paid_orders", "net_revenue_usd", "aov_usd"]) == [
        {"country": "US", "orders": 2, "paid_orders": 2, "net_revenue_usd": 76.0, "aov_usd": 38.0},
        {"country": "DE", "orders": 1, "paid_orders": 1, "net_revenue_usd": 50.0, "aov_usd": 50.0},
    ]


def test_fully_returned_order_counts_as_order_but_not_paid_order(load_fixture, golden_tables):
    from retailmetrics.models import run_models

    golden_tables["order_items"][1] = (2, 101, 10, 3, "18.00", 3)  # return all 3 units of order 101
    df = run_models(load_fixture(golden_tables))["03_country_orders_aov"]
    us = df.set_index("country").loc["US"]
    assert (us["orders"], us["paid_orders"], us["net_revenue_usd"], us["aov_usd"]) == (2, 1, 40.0, 40.0)


def test_top_products_ranked_by_net_revenue(golden_marts):
    df = golden_marts["04_top_products"]
    assert df["product_id"].tolist() == [10, 11]
    assert df["net_revenue_usd"].tolist() == [76.0, 50.0]


def test_cohort_month0_retention_is_exactly_one(golden_marts):
    df = golden_marts["05_cohort_retention"]
    month0 = df[df.month_offset == 0]
    assert not month0.empty
    assert (month0["retention_rate"] == 1.0).all()
    assert (month0["active_customers"] == month0["cohort_customers"]).all()


def test_cohort_anchors_on_first_purchase_with_spine_and_censoring(golden_marts):
    df = golden_marts["05_cohort_retention"]
    assert records(df, ["cohort_month", "cohort_customers", "month_offset", "retention_rate"]) == [
        # customer 1: first purchase Jan, active Feb, inactive Mar -> zero cell kept, not dropped
        {"cohort_month": "2024-01", "cohort_customers": 1, "month_offset": 0, "retention_rate": 1.0},
        {"cohort_month": "2024-01", "cohort_customers": 1, "month_offset": 1, "retention_rate": 1.0},
        {"cohort_month": "2024-01", "cohort_customers": 1, "month_offset": 2, "retention_rate": 0.0},
        # customer 2: cancelled Jan order ignored, so the cohort is Mar; Apr+ is beyond the data -> censored
        {"cohort_month": "2024-03", "cohort_customers": 1, "month_offset": 0, "retention_rate": 1.0},
    ]


def test_cohort_wilson_interval(golden_marts):
    # n = 1, z = 1.96: k = 1 -> [1 / (1 + z^2), 1]; k = 0 -> [0, z^2 / (1 + z^2)]
    df = golden_marts["05_cohort_retention"]
    ones = df[df.retention_rate == 1.0]
    zeros = df[df.retention_rate == 0.0]
    assert ones["retention_ci_low"].tolist() == pytest.approx([0.207] * len(ones))
    assert ones["retention_ci_high"].tolist() == pytest.approx([1.0] * len(ones))
    assert zeros[["retention_ci_low", "retention_ci_high"]].values.tolist() == [[0.0, 0.793]]
    assert (df["retention_ci_low"] <= df["retention_rate"]).all()
    assert (df["retention_rate"] <= df["retention_ci_high"]).all()


def test_country_aov_confidence_interval(golden_marts):
    # US paid orders keep 40.00 and 36.00 net: mean 38, sd = 2 * sqrt(2), half-width = 1.96 * 2 = 3.92
    df = golden_marts["diagnostics/country_aov_ci"].set_index("country")
    us = df.loc["US"]
    assert (us["paid_orders"], us["aov_usd"], us["ci_half_width_usd"]) == (2, 38.0, 3.92)
    assert (us["ci_low_usd"], us["ci_high_usd"]) == (34.08, 41.92)
    assert pd.isna(df.loc["DE", "ci_half_width_usd"])  # a single order has no sample variance


def test_monthly_activity_decomposes_growth(golden_marts):
    df = golden_marts["diagnostics/monthly_activity"]
    assert records(df, ["month", "new_signups", "cumulative_signups", "active_buyers", "orders"]) == [
        {"month": "2024-01", "new_signups": 2, "cumulative_signups": 2, "active_buyers": 1, "orders": 1},
        {"month": "2024-02", "new_signups": 0, "cumulative_signups": 2, "active_buyers": 1, "orders": 1},
        {"month": "2024-03", "new_signups": 0, "cumulative_signups": 2, "active_buyers": 1, "orders": 1},
    ]
    assert df["net_revenue_per_order_usd"].tolist() == [40.0, 36.0, 50.0]


def test_signup_cohorts_exclude_cancelled_orders(golden_marts):
    df = golden_marts["diagnostics/signup_cohorts"]
    # both customers sign up in Jan; 3 non-cancelled orders / 2 customers; window ends 2024-03-15
    assert records(df, ["signup_month", "customers", "non_cancelled_orders_per_customer"]) == [
        {"signup_month": "2024-01", "customers": 2, "non_cancelled_orders_per_customer": 1.5},
    ]
    assert df["avg_days_left"].item() == 63.0  # (70 + 55) / 2 = 62.5; DuckDB rounds half away from zero


def test_staging_measures_reconcile(load_fixture, golden_tables):
    from retailmetrics.models import build_staging

    con = load_fixture(golden_tables)
    build_staging(con)
    gross, returned, net, discount = con.execute(
        "SELECT sum(gross_revenue), sum(returned_revenue), sum(net_revenue), sum(discount_amount) FROM fct_order_lines"
    ).fetchone()
    assert (float(gross), float(returned), float(net)) == (144.0, 18.0, 126.0)
    assert float(gross) - float(returned) == float(net)
    assert float(discount) == 6.0  # order 101: 3 x (20.00 - 18.00)
