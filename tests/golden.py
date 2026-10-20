"""Golden fixture rows, small enough to verify every metric by hand.

customer 1 (US): order 100 completed in Jan, order 101 returned in Feb (1 of 3 units back)
customer 2 (DE): order 102 cancelled in Jan (must be ignored), order 103 completed in Mar
"""

from __future__ import annotations

import csv
from pathlib import Path

from retailmetrics.io import SCHEMAS

TableRows = dict[str, list[tuple]]

GOLDEN: TableRows = {
    "customers": [
        (1, "2024-01-05", "US"),
        (2, "2024-01-20", "DE"),
    ],
    "products": [
        (10, "Books", "Book A", "20.00"),
        (11, "Home", "Lamp B", "50.00"),
    ],
    "orders": [
        (100, 1, "2024-01-10", "completed"),
        (101, 1, "2024-02-03", "returned"),
        (102, 2, "2024-01-25", "cancelled"),
        (103, 2, "2024-03-15", "completed"),
    ],
    "order_items": [
        (1, 100, 10, 2, "20.00", 0),
        (2, 101, 10, 3, "18.00", 1),
        (3, 102, 11, 1, "50.00", 0),
        (4, 103, 11, 1, "50.00", 0),
    ],
}


def write_tables(data_dir: Path, tables: TableRows) -> Path:
    """Write ``tables`` as raw CSVs with the production headers."""
    data_dir.mkdir(parents=True, exist_ok=True)
    for table, rows in tables.items():
        with (data_dir / f"{table}.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, lineterminator="\n")
            writer.writerow(SCHEMAS[table])
            writer.writerows(rows)
    return data_dir
