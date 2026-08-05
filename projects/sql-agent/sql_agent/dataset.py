"""Event-sourced transactions database — the lab's generator, reproduced.

The lab builds `products.db` with `utils.create_transactions_db()`. That
generator is seeded with `random.Random(42)`, so the whole database is
deterministic — and the answers this workflow is judged against are properties
of that exact data. The sign-unaware revenue query yields -190,571.46 only for
this seed and this event sequence.

So this module reproduces the generator instead of inventing one. The order of
random calls is kept identical, including two characteristics that would change
the data if "corrected":

  - Brand and category are derived by splitting `product_name` on whitespace,
    so a "New Balance" product is stored with brand "New", category "Balance".
  - `ts` is left to SQLite's CURRENT_TIMESTAMP default, so every row lands
    inside the few seconds the build takes. No date filter can partition the
    data. Event order lives in `id`, not in `ts`.

`invariants.py` checks a generated database against known values.
"""

from __future__ import annotations

import random
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import NamedTuple

# --- types ---


class Product(NamedTuple):
    """One catalog entry. Its fields are repeated on every event row."""

    product_id: int
    name: str
    brand: str
    category: str
    color: str
    base_price: float


# --- constants ---

RANDOM_SEED = 42

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "products.db"
TABLE_NAME = "transactions"

DEFAULT_PRODUCT_COUNT = 100
DEFAULT_EVENTS_PER_PRODUCT = 50

BRANDS = ["Nike", "Adidas", "Puma", "Reebok", "New Balance"]
CATEGORIES = ["shoes", "hoodie", "t-shirt", "hat", "backpack"]
COLORS = ["black", "white", "red", "blue", "green"]

# Follow-up event mix. Sales dominate, which is what makes the sign of
# `qty_delta` decide the answer to a revenue question.
FOLLOW_UP_ACTIONS = ["restock", "sale", "price_update"]
FOLLOW_UP_WEIGHTS = [0.25, 0.6, 0.15]

BASE_PRICE_RANGE = (20.0, 150.0)
INITIAL_STOCK_RANGE = (5, 50)
RESTOCK_QTY_RANGE = (1, 25)
SALE_QTY_RANGE = (1, 10)
PRICE_DELTA_RANGE = (-5.0, 5.0)
MINIMUM_PRICE = 1.0

PRICE_DECIMALS = 2

_CREATE_TABLE_SQL = f"""
CREATE TABLE {TABLE_NAME} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    product_name TEXT NOT NULL,
    brand TEXT NOT NULL,
    category TEXT NOT NULL,
    color TEXT NOT NULL,

    action TEXT NOT NULL,            -- 'insert' | 'restock' | 'sale' | 'price_update'
    qty_delta INTEGER DEFAULT 0,     -- + for restock/insert, - for sale
    unit_price REAL,                 -- price at the time of the event (NULL for non-price events)
    notes TEXT,                      -- optional
    ts DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""

_INSERT_EVENT_SQL = f"""
INSERT INTO {TABLE_NAME} (
    product_id, product_name, brand, category, color,
    action, qty_delta, unit_price, notes
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

# --- helpers ---


def _build_catalog(rng: random.Random, product_count: int) -> list[Product]:
    """Draw the product catalog. Consumes four random values per product."""
    catalog = []
    for product_id in range(1, product_count + 1):
        name = f"{rng.choice(BRANDS)} {rng.choice(CATEGORIES)}"
        # Brand and category come from splitting the name, which puts
        # "New Balance shoes" under brand "New" / category "Balance".
        # Reproduced deliberately — see the module docstring.
        brand, category = name.split()[0], name.split()[1]
        color = rng.choice(COLORS)
        base_price = round(rng.uniform(*BASE_PRICE_RANGE), PRICE_DECIMALS)
        catalog.append(Product(product_id, name, brand, category, color, base_price))
    return catalog


def _insert_event(cursor: sqlite3.Cursor, product: Product, action: str, qty_delta: int,
                  unit_price: float | None, notes: str) -> None:
    cursor.execute(
        _INSERT_EVENT_SQL,
        (product.product_id, product.name, product.brand, product.category,
         product.color, action, qty_delta, unit_price, notes),
    )


def _seed_product_events(cursor: sqlite3.Cursor, rng: random.Random, product: Product,
                         events_per_product: int) -> None:
    initial_stock = rng.randint(*INITIAL_STOCK_RANGE)
    _insert_event(
        cursor, product, "insert", initial_stock, product.base_price,
        f"Initial insert with stock={initial_stock}, price={product.base_price}",
    )

    current_price = product.base_price
    for _ in range(events_per_product - 1):
        action = rng.choices(FOLLOW_UP_ACTIONS, weights=FOLLOW_UP_WEIGHTS, k=1)[0]

        if action == "restock":
            quantity = rng.randint(*RESTOCK_QTY_RANGE)
            # No unit_price: a restock records stock movement, not a price.
            _insert_event(cursor, product, "restock", quantity, None,
                          f"Restock +{quantity} units")
            continue

        if action == "sale":
            # Negative: a sale removes stock. This sign is what a revenue
            # query has to account for, and nothing in the schema says so.
            quantity = -rng.randint(*SALE_QTY_RANGE)
            _insert_event(cursor, product, "sale", quantity, current_price,
                          f"Sale {-quantity} units at {current_price}")
            continue

        delta = round(rng.uniform(*PRICE_DELTA_RANGE), PRICE_DECIMALS)
        current_price = max(MINIMUM_PRICE, round(current_price + delta, PRICE_DECIMALS))
        _insert_event(cursor, product, "price_update", 0, current_price,
                      f"Price update to {current_price}")


# --- main entry points ---


def create_transactions_db(
    db_path: Path | str = DEFAULT_DB_PATH,
    product_count: int = DEFAULT_PRODUCT_COUNT,
    events_per_product: int = DEFAULT_EVENTS_PER_PRODUCT,
) -> Path:
    """Create (or replace) the event-sourced database and return its path.

    Every analytic — stock level, revenue, current price — has to be derived
    from the event history in this single table. There are no views and no
    pre-computed totals.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    rng = random.Random(RANDOM_SEED)
    with closing(sqlite3.connect(db_path)) as connection:
        cursor = connection.cursor()
        cursor.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")
        cursor.execute(_CREATE_TABLE_SQL)

        for product in _build_catalog(rng, product_count):
            _seed_product_events(cursor, rng, product, events_per_product)

        connection.commit()

    return db_path


def has_transactions_table(db_path: Path | str) -> bool:
    """Whether the database exists and holds the table the workflow queries."""
    db_path = Path(db_path)
    if not db_path.exists():
        return False
    with closing(sqlite3.connect(db_path)) as connection:
        return bool(connection.execute(f"PRAGMA table_info({TABLE_NAME})").fetchall())


def get_schema(db_path: Path | str = DEFAULT_DB_PATH) -> str:
    """Return the schema string that goes into the prompt.

    Column names and types, nothing else — no value domains, no sign rules,
    no NULL conditions. That omission is the point of the exercise: the model
    cannot read the semantics off the schema, so it has to run the query and
    look at the result.
    """
    with closing(sqlite3.connect(db_path)) as connection:
        rows = connection.execute(f"PRAGMA table_info({TABLE_NAME})").fetchall()

    if not rows:
        raise ValueError(
            f"'{TABLE_NAME}' not found in {db_path}. Run create_transactions_db() first."
        )

    columns = "\n".join(f"{row[1]} ({row[2]})" for row in rows)
    return f"table name: {TABLE_NAME}\n{columns}"


def ensure_database(db_path: Path | str = DEFAULT_DB_PATH) -> Path:
    """Create the database unless a usable one is already there.

    Checks for the table rather than the file: an empty or truncated
    `products.db` would otherwise be handed to the workflow, which would then
    fail with a confusing SQL error instead of just being rebuilt. Rebuilding
    costs nothing — the generator is deterministic.
    """
    db_path = Path(db_path)
    if has_transactions_table(db_path):
        return db_path
    return create_transactions_db(db_path)
