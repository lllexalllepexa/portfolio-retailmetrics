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
