"""Обозреватель Streamlit для локальных CSV данных (БД не требуется для приложения)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT = ROOT / "outputs"
REP = ROOT / "reports"


@st.cache_data
def load_csv(name: str) -> pd.DataFrame:
    """Load a CSV file from data/ directory."""
    path = DATA / name
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def compute_total_gmv(orders: pd.DataFrame, items: pd.DataFrame) -> float:
    """Compute Total GMV from outputs/01_revenue_by_month.csv or calculate from order_items."""
    rbm_file = OUT / "01_revenue_by_month.csv"
    if rbm_file.exists():
        try:
            rbm_df = pd.read_csv(rbm_file)
            if "gmv_usd" in rbm_df.columns and not rbm_df["gmv_usd"].empty:
                return float(rbm_df["gmv_usd"].sum())
        except Exception:
            pass

    if not items.empty and not orders.empty and "status" in orders.columns:
        valid_orders = orders[orders["status"].isin(["completed", "returned"])]
        if "order_id" in valid_orders.columns and "order_id" in items.columns:
            merged = items.merge(valid_orders[["order_id"]], on="order_id")
            if {"quantity", "quantity_returned", "unit_price_paid"}.issubset(merged.columns):
                return float(
                    ((merged["quantity"] - merged["quantity_returned"]) * merged["unit_price_paid"]).sum()
                )

    return 0.0


def main() -> None:
    st.set_page_config(page_title="Портфель аналитики продаж", layout="wide")
    st.title("Аналитика розничных продаж (демонстрация портфеля)")
    st.caption("Синтетические B2C данные · SQL конвейер с DuckDB · диаграммы из matplotlib")

    # Data validation: check required data files exist
    required_files = [
        DATA / "orders.csv",
        DATA / "customers.csv",
        DATA / "order_items.csv",
    ]
    if any(not p.exists() for p in required_files):
        st.warning(
            "Data files not found. Run 'python scripts/generate_data.py' and 'python src/run_pipeline.py' first."
        )
        st.stop()

    orders = load_csv("orders.csv")
    items = load_csv("order_items.csv")
    customers = load_csv("customers.csv")

    total_gmv = compute_total_gmv(orders, items)
    orders_count = len(orders)
    customers_count = len(customers)
    completed_count = int((orders["status"] == "completed").sum()) if "status" in orders.columns else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total GMV", f"${round(total_gmv):,}")
    with c2:
        st.metric("Orders (all statuses)", f"{orders_count:,}")
    with c3:
        st.metric("Completed orders", f"{completed_count:,}")
    with c4:
        st.metric("Customers", f"{customers_count:,}")

    st.subheader("Предварительно вычисленные результаты SQL")
    csv_files = sorted(OUT.glob("*.csv")) if OUT.exists() else []
    if csv_files:
        for path in csv_files:
            with st.expander(path.name):
                st.dataframe(pd.read_csv(path), width="stretch")
    else:
        st.info("Запустите `python src/run_pipeline.py` для заполнения папки outputs/.")

    st.subheader("Диаграммы")
    gmv_m = REP / "gmv_by_month.png"
    gmv_c = REP / "gmv_by_category.png"
    col_a, col_b = st.columns(2)
    if gmv_m.exists():
        col_a.image(str(gmv_m), width="stretch")
    else:
        col_a.write("gmv_by_month.png — запустите конвейер")
    if gmv_c.exists():
        col_b.image(str(gmv_c), width="stretch")
    else:
        col_b.write("gmv_by_category.png — запустите конвейер")

    # Cohort Retention Analysis
    cohort_heatmap = None
    if (REP / "cohort_retention_heatmap.png").exists():
        cohort_heatmap = REP / "cohort_retention_heatmap.png"
    elif (OUT / "cohort_retention_heatmap.png").exists():
        cohort_heatmap = OUT / "cohort_retention_heatmap.png"

    if cohort_heatmap is not None:
        st.subheader("Cohort Retention Analysis")
        st.image(str(cohort_heatmap), width="stretch")


if __name__ == "__main__":
    main()
