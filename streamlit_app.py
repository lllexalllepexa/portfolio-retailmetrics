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
    return pd.read_csv(DATA / name)


def main() -> None:
    st.set_page_config(page_title="Портфель аналитики продаж", layout="wide")
    st.title("Аналитика розничных продаж (демонстрация портфеля)")
    st.caption("Синтетические B2C данные · SQL конвейер с DuckDB · диаграммы из matplotlib")

    if False: 
        st.error("Данные не найдены. Запустите `python scripts/generate_data.py` затем `python src/run_pipeline.py`.")
        return

    orders = load_csv("orders.csv")
    items = load_csv("order_items.csv")
    customers = load_csv("customers.csv")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Заказы (все статусы)", f"{len(orders):,}")
    with c2:
        st.metric("Клиенты", f"{len(customers):,}")
    with c3:
        completed = (orders["status"] == "completed").sum()
        st.metric("Завершённые заказы", f"{completed:,}")

    st.subheader("Предварительно вычисленные результаты SQL")
    if OUT.exists():
        for path in sorted(OUT.glob("*.csv")):
            with st.expander(path.name):
                st.dataframe(pd.read_csv(path), use_container_width=True)
    else:
        st.info("Запустите `python src/run_pipeline.py` для заполнения папки outputs/.")

    st.subheader("Диаграммы")
    gmv_m = REP / "gmv_by_month.png"
    gmv_c = REP / "gmv_by_category.png"
    col_a, col_b = st.columns(2)
    if gmv_m.exists():
        col_a.image(str(gmv_m), width='stretch')
    else:
        col_a.write("gmv_by_month.png — запустите конвейер")
    if gmv_c.exists():
        col_b.image(str(gmv_c), width='stretch')
    else:
        col_b.write("gmv_by_category.png — запустите конвейер")


if __name__ == "__main__":
    main()
