"""Coffee sales dataset — generator and loader.

The lab ships `coffee_sales.csv` next to its notebook and we could not obtain it,
so this module regenerates one with the same contract.

What matters is not the CSV but what `load_and_prepare_data` returns: the
LLM-generated plotting code sees nothing except that DataFrame, and the lab
prompt promises it exactly nine columns. `SCHEMA_COLUMNS` is that promise, and
`load_and_prepare_data` refuses to return anything else.

Observed values are reproduced exactly — see PLAN.md §5 for how they were read
off the lab's rendered `df.sample(n=5)` table.
"""

from __future__ import annotations

import math
import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

# --- constants ---

RANDOM_SEED = 20260804

# The nine columns the lab prompt declares, in the order the lab renders them.
RAW_COLUMNS = ["date", "time", "cash_type", "card", "price", "coffee_name"]
DERIVED_COLUMNS = ["quarter", "month", "year"]
SCHEMA_COLUMNS = RAW_COLUMNS + DERIVED_COLUMNS

# Both Q1s must be complete: the lab instruction compares Q1 2024 with Q1 2025.
START_DATE = date(2024, 1, 1)
END_DATE = date(2025, 3, 31)
TOTAL_SPAN_DAYS = (END_DATE - START_DATE).days

# The lab's sample shows Latte at 3.282 in July 2024 and 3.576 in December 2024,
# so a price rise happened in between. Espresso 1.812 (August) is pre-rise;
# Cortado 2.596 (December) and Americano 2.596 (February) are post-rise.
PRICE_RISE_DATE = date(2024, 10, 1)

PRICES_BEFORE_RISE = {
    "Espresso": 1.812,
    "Americano": 2.382,
    "Cortado": 2.382,
    "Americano with Milk": 2.832,
    "Cappuccino": 3.282,
    "Cocoa": 3.282,
    "Hot Chocolate": 3.282,
    "Latte": 3.282,
}
PRICES_AFTER_RISE = {
    "Espresso": 1.986,
    "Americano": 2.596,
    "Cortado": 2.596,
    "Americano with Milk": 3.086,
    "Cappuccino": 3.576,
    "Cocoa": 3.576,
    "Hot Chocolate": 3.576,
    "Latte": 3.576,
}

# The five (drink, date, price) triples readable from the lab's rendered
# `df.sample(n=5)` table — the only ground truth we have for prices. What must
# match is the *price* on that date; whether a row happens to exist there is a
# random draw and not something to reproduce.
OBSERVED_PRICES = (
    ("Latte", date(2024, 7, 19), 3.282),
    ("Espresso", date(2024, 8, 7), 1.812),
    ("Latte", date(2024, 12, 4), 3.576),
    ("Cortado", date(2024, 12, 5), 2.596),
    ("Americano", date(2025, 2, 10), 2.596),
)

# Eight drinks, confirmed from the V2 legend on the lecture slide. Every one of
# them must appear in both Q1s: the lab's V1 code inner-joins the two years, so
# a drink missing from either side would silently vanish from the chart.
DRINK_WEIGHTS = {
    "Latte": 0.22,
    "Americano with Milk": 0.20,
    "Americano": 0.17,
    "Cappuccino": 0.13,
    "Cortado": 0.10,
    "Hot Chocolate": 0.07,
    "Espresso": 0.06,
    "Cocoa": 0.05,
}

# Sales grow over the period so that Q1 2025 outsells Q1 2024 — without a
# quantity column the only way to move volume is to add rows. These are
# *weekday* rates; the realised daily average is lower because weekends are
# damped by WEEKEND_SALES_RATIO.
WEEKDAY_SALES_AT_START = 9
WEEKDAY_SALES_AT_END = 19
WEEKEND_SALES_RATIO = 0.55
# Jitter scales with demand. A fixed spread would push quiet weekend days below
# zero and pile them onto the floor of one sale a day.
DAILY_SALES_JITTER_RATIO = 0.30
MIN_SALES_PER_DAY = 1

# Vending machine in an office lobby: morning rush, smaller afternoon bump.
HOUR_WEIGHTS = {
    7: 0.04, 8: 0.11, 9: 0.13, 10: 0.12, 11: 0.09, 12: 0.07, 13: 0.06,
    14: 0.08, 15: 0.08, 16: 0.06, 17: 0.05, 18: 0.04, 19: 0.03, 20: 0.04,
}
# Split out once: `_random_time` runs per transaction, thousands of times.
HOURS = list(HOUR_WEIGHTS)
HOUR_WEIGHT_VALUES = list(HOUR_WEIGHTS.values())
MINUTES_PER_HOUR = 60

CARD_PAYMENT_SHARE = 0.93
DISTINCT_CARD_COUNT = 1200
CASH_CARD_VALUE = ""  # cash rows carry no card id

# Written to first, renamed into place only once the data validates.
PENDING_SUFFIX = ".pending"

SATURDAY = 5

# What the lab instruction compares. `validate_dataset` enforces that this
# comparison is actually answerable from the generated data.
COMPARISON_QUARTER = 1
BASELINE_YEAR = 2024
GROWTH_YEAR = 2025
COMPARISON_YEARS = (BASELINE_YEAR, GROWTH_YEAR)

# The lab's own dataset, when it can be found, in preference to a generated one.
LAB_DATASET_PATH = Path(__file__).resolve().parents[3] / "labs" / "module-2" / "coffee_sales.csv"
GENERATED_DATASET_PATH = Path(__file__).resolve().parents[1] / "data" / "coffee_sales.csv"


# --- helpers ---


def _daily_sales_mean(day: date) -> float:
    """Linearly interpolated demand, damped on weekends."""
    elapsed_ratio = (day - START_DATE).days / TOTAL_SPAN_DAYS
    growth = WEEKDAY_SALES_AT_START + elapsed_ratio * (WEEKDAY_SALES_AT_END - WEEKDAY_SALES_AT_START)

    is_weekend = day.weekday() >= SATURDAY
    return growth * WEEKEND_SALES_RATIO if is_weekend else growth


def _sales_count(rng: random.Random, day: date) -> int:
    mean = _daily_sales_mean(day)
    jittered = rng.gauss(mean, mean * DAILY_SALES_JITTER_RATIO)
    return max(MIN_SALES_PER_DAY, round(jittered))


def _random_time(rng: random.Random) -> str:
    hour = rng.choices(HOURS, weights=HOUR_WEIGHT_VALUES, k=1)[0]
    minute = rng.randrange(MINUTES_PER_HOUR)
    return f"{hour:02d}:{minute:02d}"


def _price_of(drink: str, day: date) -> float:
    table = PRICES_AFTER_RISE if day >= PRICE_RISE_DATE else PRICES_BEFORE_RISE
    return table[drink]


def _payment(rng: random.Random) -> tuple[str, str]:
    """Return (cash_type, card). Cash transactions have no card id."""
    pays_by_card = rng.random() < CARD_PAYMENT_SHARE
    if not pays_by_card:
        return "cash", CASH_CARD_VALUE

    card_number = rng.randrange(DISTINCT_CARD_COUNT)
    return "card", f"ANON-0000-0000-{card_number:04d}"


def _validate_price_tables() -> None:
    """Check the price tables against the lab's sample table.

    Static: depends only on the constants, not on any generated data. Guards
    against PRICE_RISE_DATE or either table drifting off the only evidence.
    """
    for drink, day, expected in OBSERVED_PRICES:
        actual = _price_of(drink, day)
        if not math.isclose(actual, expected):
            raise ValueError(
                f"{drink} on {day} prices at {actual}, but the lab's sample table shows {expected}."
            )


def _validate_first_quarters(df: pd.DataFrame) -> None:
    """Check that the lab's Q1-over-Q1 comparison is answerable from `df`.

    Deliberately not checked: that both quarters span three months. An earlier
    version required it, and the lab's own dataset fails that check — it starts
    on 2024-03-01, so Q1 2024 is March alone. The invariant was a guess about
    what the data ought to look like, not something the lab's code needs.
    """
    expected_drinks = set(DRINK_WEIGHTS)
    row_counts = {}

    for year in COMPARISON_YEARS:
        rows = df[(df["year"] == year) & (df["quarter"] == COMPARISON_QUARTER)]
        if rows.empty:
            raise ValueError(f"Q{COMPARISON_QUARTER} {year} is empty — the lab instruction compares it.")

        drinks = set(rows["coffee_name"].unique())
        if drinks != expected_drinks:
            raise ValueError(
                f"Q{COMPARISON_QUARTER} {year} is missing {sorted(expected_drinks - drinks)}. "
                f"The lab's V1 code inner-joins on coffee_name, so it would drop silently."
            )
        row_counts[year] = len(rows)

    grew = row_counts[GROWTH_YEAR] > row_counts[BASELINE_YEAR]
    if not grew:
        raise ValueError(
            f"Q{COMPARISON_QUARTER} {GROWTH_YEAR} ({row_counts[GROWTH_YEAR]} rows) does not exceed "
            f"{BASELINE_YEAR} ({row_counts[BASELINE_YEAR]} rows); the comparison shows no growth."
        )


# --- main export ---


def generate_dataset(seed: int = RANDOM_SEED) -> pd.DataFrame:
    """Build the raw six-column table, one row per transaction.

    There is no quantity column, so one row means one cup. Volume differences
    between periods come from the number of rows, never from a multiplier.
    """
    rng = random.Random(seed)
    drinks = list(DRINK_WEIGHTS)
    drink_weights = [DRINK_WEIGHTS[d] for d in drinks]

    rows = []
    day = START_DATE
    while day <= END_DATE:
        for _ in range(_sales_count(rng, day)):
            drink = rng.choices(drinks, weights=drink_weights, k=1)[0]
            cash_type, card = _payment(rng)
            rows.append(
                {
                    "date": day.isoformat(),
                    "time": _random_time(rng),
                    "cash_type": cash_type,
                    "card": card,
                    "price": _price_of(drink, day),
                    "coffee_name": drink,
                }
            )
        day += timedelta(days=1)

    return pd.DataFrame(rows, columns=RAW_COLUMNS)


def resolve_dataset_path() -> Path:
    """Return the dataset to work with, preferring the lab's own file.

    The generated dataset was built before the lab's `coffee_sales.csv` turned
    up. Now that the real one is here it is the better default — it is what the
    lab's charts were produced from, so outputs are comparable. The generator
    stays as a fallback for anyone without the course files.

    Raises:
        FileNotFoundError: neither dataset exists.
    """
    if LAB_DATASET_PATH.exists():
        return LAB_DATASET_PATH
    if GENERATED_DATASET_PATH.exists():
        return GENERATED_DATASET_PATH

    raise FileNotFoundError(
        f"no dataset at {LAB_DATASET_PATH} or {GENERATED_DATASET_PATH} — "
        f"generate one with `python -m chart_agent.dataset`."
    )


def load_and_prepare_data(path: str | Path) -> pd.DataFrame:
    """Load the CSV and derive `quarter`, `month`, `year` — the lab's contract.

    `date` comes back as datetime64 and `time` stays a string; the lab prompt
    warns the model never to concatenate them, so they must not be pre-joined
    here either.

    Raises:
        FileNotFoundError: the CSV is missing (run `write_dataset` first).
        ValueError: the loaded frame does not match `SCHEMA_COLUMNS`.
    """
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(
            f"{source} not found — generate it with "
            f"`python -m chart_agent.dataset` first."
        )

    df = pd.read_csv(source, parse_dates=["date"])
    # Cash rows have an empty card field; keep the column textual rather than
    # letting pandas turn it into a float NaN column.
    df["card"] = df["card"].fillna(CASH_CARD_VALUE).astype(str)

    df["quarter"] = df["date"].dt.quarter
    df["month"] = df["date"].dt.month
    df["year"] = df["date"].dt.year

    has_expected_schema = set(df.columns) == set(SCHEMA_COLUMNS)
    if not has_expected_schema:
        unexpected = sorted(set(df.columns) - set(SCHEMA_COLUMNS))
        missing = sorted(set(SCHEMA_COLUMNS) - set(df.columns))
        raise ValueError(
            f"schema mismatch — missing={missing}, unexpected={unexpected}. "
            f"The lab prompt promises exactly {SCHEMA_COLUMNS}."
        )

    return df[SCHEMA_COLUMNS]


def validate_dataset(df: pd.DataFrame) -> None:
    """Assert the invariants the lab's own V1 code depends on.

    The generated V1 code inner-joins the two years on `coffee_name`, so a drink
    missing from either quarter would vanish from the chart without any error.
    Tuning the seed or the weights must not be able to break that quietly.

    Raises:
        ValueError: on the first invariant that does not hold.
    """
    _validate_price_tables()
    _validate_first_quarters(df)


def write_dataset(path: str | Path, seed: int = RANDOM_SEED) -> Path:
    """Generate, validate, then publish the CSV. Returns the path written.

    Validation runs against a reloaded file, so what gets checked is a real
    CSV round trip rather than the in-memory frame that produced it. Every
    caller gets the guarantee — leaving the check to `__main__` would let a
    tuned seed ship a dataset the lab's V1 code cannot chart.

    The file is built beside the target and moved into place only after it
    validates, so a failed run never leaves a broken dataset for the next one
    to pick up silently.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_suffix(target.suffix + PENDING_SUFFIX)

    try:
        generate_dataset(seed).to_csv(staging, index=False)
        validate_dataset(load_and_prepare_data(staging))
    except Exception:
        staging.unlink(missing_ok=True)
        raise

    staging.replace(target)
    return target


if __name__ == "__main__":
    written = write_dataset(Path(__file__).resolve().parents[1] / "data" / "coffee_sales.csv")
    frame = load_and_prepare_data(written)
    print(f"{written}  rows={len(frame):,}  columns={len(frame.columns)}  invariants OK")
