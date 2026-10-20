"""Generate reproducible synthetic e-commerce CSVs for the portfolio project.

Run: python scripts/generate_data.py [--out DIR] [--seed N]

The distributions are deliberately simple (uniform signup dates Jan-Apr, uniform order dates
between signup and the end of the window). README "Diagnosing Synthetic Artifacts" explains
which downstream trends are produced by these mechanics rather than by customer behavior.
"""

from __future__ import annotations

import argparse
import csv
import logging
import random
from datetime import date, timedelta
from pathlib import Path
from typing import TypedDict

log = logging.getLogger(__name__)

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "data"

CATEGORIES = ["Electronics", "Home", "Apparel", "Sports", "Books"]
COUNTRIES = ["US", "DE", "FR", "PL", "GB"]
COUNTRY_WEIGHTS = [0.45, 0.15, 0.12, 0.10, 0.18]
ORDERS_PER_CUSTOMER = [0, 1, 2, 3, 4, 5]
ORDERS_PER_CUSTOMER_WEIGHTS = [0.12, 0.35, 0.25, 0.15, 0.08, 0.05]
STATUSES = ["completed", "returned", "cancelled"]
STATUS_WEIGHTS = [0.88, 0.07, 0.05]
DISCOUNTS = [0.0, 0.0, 0.05, 0.1, 0.15]

N_CUSTOMERS = 1200
PRODUCTS_PER_CATEGORY = 8
START = date(2024, 1, 1)
END = date(2024, 6, 30)
SIGNUP_WINDOW_DAYS = 120


class Product(TypedDict):
    product_id: int
    category: str
    name: str
    list_price: float


class Customer(TypedDict):
    customer_id: int
    signup_date: str
    country: str


class Order(TypedDict):
    order_id: int
    customer_id: int
    order_date: str
    status: str


class OrderItem(TypedDict):
    order_line_id: int
    order_id: int
    product_id: int
    quantity: int
    unit_price_paid: float
    quantity_returned: int


def returned_units(status: str, qty: int, rng: random.Random) -> int:
    """Full return 60% of the time, otherwise a partial return of at least one unit."""
    if status != "returned":
        return 0
    return qty if rng.random() < 0.6 else rng.randint(1, qty)


def make_products(rng: random.Random) -> list[Product]:
    products: list[Product] = []
    for cat in CATEGORIES:
        for i in range(1, PRODUCTS_PER_CATEGORY + 1):
            products.append(
                Product(
                    product_id=len(products) + 1,
                    category=cat,
                    name=f"{cat} item {i}",
                    list_price=round(rng.uniform(9.99, 299.99), 2),
                )
            )
    return products


def make_customers(rng: random.Random) -> list[Customer]:
    return [
        Customer(
            customer_id=cid,
            signup_date=(START + timedelta(days=rng.randint(0, SIGNUP_WINDOW_DAYS))).isoformat(),
            country=rng.choices(COUNTRIES, weights=COUNTRY_WEIGHTS, k=1)[0],
        )
        for cid in range(1, N_CUSTOMERS + 1)
    ]


def make_orders(
    customers: list[Customer], products: list[Product], rng: random.Random
) -> tuple[list[Order], list[OrderItem]]:
    orders: list[Order] = []
    items: list[OrderItem] = []
    for cust in customers:
        signup = date.fromisoformat(cust["signup_date"])
        n_orders = rng.choices(ORDERS_PER_CUSTOMER, weights=ORDERS_PER_CUSTOMER_WEIGHTS, k=1)[0]
        for _ in range(n_orders):
            order_id = len(orders) + 1
            order_date = signup + timedelta(days=rng.randint(0, (END - signup).days))
            status = rng.choices(STATUSES, weights=STATUS_WEIGHTS, k=1)[0]
            orders.append(
                Order(
                    order_id=order_id, customer_id=cust["customer_id"], order_date=order_date.isoformat(), status=status
                )
            )
            for _ in range(rng.randint(1, 4)):
                product = rng.choice(products)
                qty = rng.randint(1, 3)
                discount = rng.choice(DISCOUNTS)
                items.append(
                    OrderItem(
                        order_line_id=len(items) + 1,
                        order_id=order_id,
                        product_id=product["product_id"],
                        quantity=qty,
                        unit_price_paid=round(product["list_price"] * (1 - discount), 2),
                        quantity_returned=returned_units(status, qty, rng),
                    )
                )
    return orders, items


def write_csv(path: Path, rows: list, fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def generate(out_dir: Path = DEFAULT_OUT, seed: int = 42) -> dict[str, int]:
    """Write the four raw CSVs to ``out_dir`` and return row counts per table."""
    rng = random.Random(seed)
    products = make_products(rng)
    customers = make_customers(rng)
    orders, items = make_orders(customers, products, rng)

    out_dir.mkdir(parents=True, exist_ok=True)
    tables: dict[str, tuple[list, type]] = {
        "products": (products, Product),
        "customers": (customers, Customer),
        "orders": (orders, Order),
        "order_items": (items, OrderItem),
    }
    for name, (rows, row_type) in tables.items():
        write_csv(out_dir / f"{name}.csv", rows, list(row_type.__annotations__))
    return {name: len(rows) for name, (rows, _) in tables.items()}


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Generate synthetic retail CSVs.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    counts = generate(args.out, args.seed)
    log.info("Wrote %s -> %s", ", ".join(f"{n} {t}" for t, n in counts.items()), args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
