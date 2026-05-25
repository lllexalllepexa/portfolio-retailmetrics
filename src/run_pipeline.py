"""Load CSVs into DuckDB, run all SQL analytics, export CSVs and charts."""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SQL = ROOT / "sql"
OUT = ROOT / "outputs"
REP = ROOT / "reports"


def load_tables(con: duckdb.DuckDBPyConnection) -> None:
    for table, fname in [
        ("customers", "customers.csv"),
        ("orders", "orders.csv"),
        ("order_items", "order_items.csv"),
        ("products", "products.csv"),
    ]:
        path = DATA / fname
        if not path.exists():
            raise FileNotFoundError(f"Missing {path}. Run: python scripts/generate_data.py")
        posix_path = path.resolve().as_posix().replace("'", "''")
        con.execute(
            f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_csv_auto('{posix_path}');"
        )


def run_sql_file(con: duckdb.DuckDBPyConnection, path: Path) -> pd.DataFrame:
    sql_text = path.read_text(encoding="utf-8")
    return con.execute(sql_text).df()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    REP.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(database=":memory:")
    load_tables(con)

    results: dict[str, pd.DataFrame] = {}
    for p in sorted(SQL.glob("*.sql")):
        name = p.stem
        df = run_sql_file(con, p)
        results[name] = df
        df.to_csv(OUT / f"{name}.csv", index=False)

    # Charts
    rbm = results["01_revenue_by_month"]
    if not rbm.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(rbm["order_month"].astype(str), rbm["gmv_usd"], color="#2c5282")
        ax.set_title("GMV by month (USD)")
        ax.set_xlabel("Month")
        ax.set_ylabel("GMV")
        plt.xticks(rotation=45, ha="right")
        fig.tight_layout()
        fig.savefig(REP / "gmv_by_month.png", dpi=150)
        plt.close(fig)

    rbc = results["02_revenue_by_category"]
    if not rbc.empty:
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.barh(rbc["category"], rbc["gmv_usd"], color="#276749")
        ax.invert_yaxis()
        ax.set_title("GMV by category (USD)")
        fig.tight_layout()
        fig.savefig(REP / "gmv_by_category.png", dpi=150)
        plt.close(fig)

    print(f"Wrote {len(results)} result tables -> {OUT}")
    print(f"Wrote charts -> {REP}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
