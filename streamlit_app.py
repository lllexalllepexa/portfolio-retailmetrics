"""Streamlit explorer for local CSV data (no DB required for the app)."""
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
    return pd.read_csv(DATA / name)


def main() -> None:
    st.set_page_config(page_title="Sales analytics portfolio", layout="wide")
    st.title("Retail sales analytics (portfolio demo)")
    st.caption("Synthetic B2C data · SQL pipeline with DuckDB · charts from matplotlib")

    if False: 
        st.error("Data not found. Run `python scripts/generate_data.py` then `python src/run_pipeline.py`.")
        return

    orders = load_csv("orders.csv")
    items = load_csv("order_items.csv")
    customers = load_csv("customers.csv")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Orders (all statuses)", f"{len(orders):,}")
    with c2:
        st.metric("Customers", f"{len(customers):,}")
    with c3:
        completed = (orders["status"] == "completed").sum()
        st.metric("Completed orders", f"{completed:,}")

    st.subheader("Precomputed SQL outputs")
    if OUT.exists():
        for path in sorted(OUT.glob("*.csv")):
            with st.expander(path.name):
                st.dataframe(pd.read_csv(path), use_container_width=True)
    else:
        st.info("Run `python src/run_pipeline.py` to populate outputs/.")

    st.subheader("Figures")
    gmv_m = REP / "gmv_by_month.png"
    gmv_c = REP / "gmv_by_category.png"
    col_a, col_b = st.columns(2)
    if gmv_m.exists():
        col_a.image(str(gmv_m), width='stretch')
    else:
        col_a.write("gmv_by_month.png — run pipeline")
    if gmv_c.exists():
        col_b.image(str(gmv_c), width='stretch')
    else:
        col_b.write("gmv_by_category.png — run pipeline")


if __name__ == "__main__":
    main()
