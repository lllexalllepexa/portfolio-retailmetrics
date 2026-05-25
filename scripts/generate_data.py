"""
Generate reproducible synthetic e-commerce CSVs for the portfolio project.
Run: python scripts/generate_data.py
"""
from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

CATEGORIES = ["Electronics", "Home", "Apparel", "Sports", "Books"]


def main() -> None:
    random.seed(42)
    DATA.mkdir(parents=True, exist_ok=True)

    start_global = date(2024, 1, 1)
    end_global = date(2024, 6, 30)

    products: list[dict] = []
    pid = 1
    for cat in CATEGORIES:
        for i in range(1, 9):
            products.append(
                {
                    "product_id": pid,
                    "category": cat,
                    "name": f"{cat} item {i}",
                    "list_price": round(random.uniform(9.99, 299.99), 2),
                }
            )
            pid += 1

    customers: list[dict] = []
    for cid in range(1, 1201):
        signup = start_global + timedelta(days=random.randint(0, 120))
        customers.append(
            {
                "customer_id": cid,
                "signup_date": signup.isoformat(),
                "country": random.choices(
                    ["US", "DE", "FR", "PL", "GB"],
                    weights=[0.45, 0.15, 0.12, 0.1, 0.18],
                    k=1,
                )[0],
            }
        )

    orders: list[dict] = []
    order_items: list[dict] = []
    order_id = 1
    line_id = 1

    for cid in range(1, 1201):
        n_orders = random.choices([0, 1, 2, 3, 4, 5], weights=[0.12, 0.35, 0.25, 0.15, 0.08, 0.05], k=1)[0]
        cust = customers[cid - 1]
        signup = date.fromisoformat(cust["signup_date"])
        for _ in range(n_orders):
            order_date = max(
                signup,
                min(
                    end_global,
                    signup + timedelta(days=random.randint(0, (end_global - signup).days or 1)),
                ),
            )
            status = random.choices(["completed", "returned", "cancelled"], weights=[0.88, 0.07, 0.05], k=1)[0]
            orders.append(
                {
                    "order_id": order_id,
                    "customer_id": cid,
                    "order_date": order_date.isoformat(),
                    "status": status,
                }
            )
            n_lines = random.randint(1, 4)
            for _l in range(n_lines):
                p = random.choice(products)
                qty = random.randint(1, 3)
                discount = random.choice([0.0, 0.0, 0.05, 0.1, 0.15])
                unit = round(p["list_price"] * (1 - discount), 2)
                if status == "returned" and random.random() < 0.4:
                    qty_returned = random.randint(0, qty)
                else:
                    qty_returned = qty if status == "returned" else 0
                order_items.append(
                    {
                        "order_line_id": line_id,
                        "order_id": order_id,
                        "product_id": p["product_id"],
                        "quantity": qty,
                        "unit_price_paid": unit,
                        "quantity_returned": qty_returned if status == "returned" else 0,
                    }
                )
                line_id += 1
            order_id += 1

    def write_csv(name: str, rows: list[dict], fieldnames: list[str]) -> None:
        path = DATA / name
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)

    write_csv(
        "products.csv",
        products,
        ["product_id", "category", "name", "list_price"],
    )
    write_csv(
        "customers.csv",
        customers,
        ["customer_id", "signup_date", "country"],
    )
    write_csv(
        "orders.csv",
        orders,
        ["order_id", "customer_id", "order_date", "status"],
    )
    write_csv(
        "order_items.csv",
        order_items,
        ["order_line_id", "order_id", "product_id", "quantity", "unit_price_paid", "quantity_returned"],
    )

    print(f"Wrote {len(products)} products, {len(customers)} customers, {len(orders)} orders, {len(order_items)} order lines -> {DATA}")


if __name__ == "__main__":
    main()
