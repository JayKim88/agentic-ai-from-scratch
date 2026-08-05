"""Known-good properties of the generated database.

Every success rate this project reports is measured against these values, so
they are pinned here and checked before anything else runs. If the generator
drifts, the numbers below stop matching and every later comparison would be
measuring different data without saying so.

The expected values were read off a database built by the lab's own generator.
`check_dataset()` re-derives them with SQL and raises on the first mismatch.

Run directly to verify:

    python -m sql_agent.invariants
"""

from __future__ import annotations

import importlib.util
import sqlite3
import tempfile
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from sql_agent.dataset import DEFAULT_DB_PATH, create_transactions_db

# --- types ---


@dataclass(frozen=True)
class Expectation:
    """One evaluation question and the answer a correct query must produce.

    `question` is the exact text the model is asked — the scorer and the
    evaluation set read it from here so the wording lives in one place.
    `reference_sql` is our hand-written answer, used to re-derive `key` and
    `value` against a freshly built database.

    `key` is the grouping value the first row must carry, as a string so that
    a model returning 34 and one returning "34" both match; it is None when
    the question asks for a bare aggregate.
    """

    question: str
    reference_sql: str
    key: str | None
    value: float


# --- constants ---

VALUE_TOLERANCE = 0.01

# The lab's own generator, kept alongside its notebook. Used to prove our
# reproduction is exact rather than merely close.
LAB_UTILS_PATH = Path(__file__).resolve().parents[3] / "labs" / "module-2" / "sql" / "utils.py"

# ts is CURRENT_TIMESTAMP at build time, so two databases built minutes apart
# differ there and only there.
GENERATED_AT_COLUMN = "ts"

TOTAL_ROWS = 5_000

# `ts` defaults to CURRENT_TIMESTAMP, which has one-second resolution, so every
# row lands inside the few seconds the build takes. The count of distinct values
# is not fixed — it is 1 or 2 depending on whether the insert loop crosses a
# second boundary — but the span always is. Anything coarser than a second, and
# every date filter a query might write, sees a single instant.
BUILD_WINDOW_SECONDS = 5

ACTION_COUNTS = {"insert": 100, "price_update": 723, "restock": 1_258, "sale": 2_919}

# The lab's own figure. A revenue query that multiplies the raw qty_delta gets
# this, and the ranking it produces is the exact reverse of the right one.
SIGN_UNAWARE_TOP_COLOR = "blue"
SIGN_UNAWARE_TOP_VALUE = -190_571.46

SIGN_AWARE_TOP_COLOR = "white"
SIGN_AWARE_TOP_VALUE = 358_315.09

# Same expression without the action filter. Recorded because it does *not*
# match the lab's figure, which is how we know the lab's V1 filtered on sales.
UNFILTERED_TOP_VALUE = -150_511.18

# Reference queries alias their columns so a single reader can pull (key, value)
# out of any of them regardless of what was grouped.
_SALES_BY = """
SELECT {group_by} AS group_key, SUM({amount}) AS answer
FROM transactions WHERE action = 'sale'
GROUP BY {group_by} ORDER BY answer DESC LIMIT 1
"""

# Evaluation questions. Each one was run before being written down: a question
# whose answer is NULL or an empty result cannot score anything.
EXPECTATIONS: tuple[Expectation, ...] = (
    Expectation(
        "Which color of product has the highest total sales? Consider sale events only.",
        _SALES_BY.format(group_by="color", amount="ABS(qty_delta) * unit_price"),
        SIGN_AWARE_TOP_COLOR, SIGN_AWARE_TOP_VALUE,
    ),
    Expectation(
        "Which brand generated the most sales revenue? Consider sale events only.",
        _SALES_BY.format(group_by="brand", amount="ABS(qty_delta) * unit_price"),
        "Nike", 384_355.53,
    ),
    Expectation(
        "What is the current price of product 1?",
        "SELECT NULL AS group_key, unit_price AS answer FROM transactions "
        "WHERE product_id = 1 AND unit_price IS NOT NULL ORDER BY id DESC LIMIT 1",
        None, 57.16,
    ),
    Expectation(
        "Which product has the highest current stock?",
        "SELECT product_id AS group_key, SUM(qty_delta) AS answer FROM transactions "
        "GROUP BY product_id ORDER BY answer DESC LIMIT 1",
        "34", 197,
    ),
    Expectation(
        "How many sale events are there?",
        "SELECT NULL AS group_key, COUNT(*) AS answer FROM transactions WHERE action = 'sale'",
        None, 2_919,
    ),
    Expectation(
        "How many units were restocked in total?",
        "SELECT NULL AS group_key, SUM(qty_delta) AS answer FROM transactions "
        "WHERE action = 'restock'",
        None, 16_753,
    ),
)

# --- helpers ---


class InvariantError(AssertionError):
    """A generated database does not match the values this project measures against."""


def _scalar(connection: sqlite3.Connection, sql: str):
    row = connection.execute(sql).fetchone()
    return None if row is None else row[0]


def _require(is_satisfied: bool, message: str) -> None:
    if not is_satisfied:
        raise InvariantError(message)


def _check_shape(connection: sqlite3.Connection) -> None:
    row_count = _scalar(connection, "SELECT COUNT(*) FROM transactions")
    _require(row_count == TOTAL_ROWS, f"row count {row_count} != {TOTAL_ROWS}")

    counts = dict(connection.execute(
        "SELECT action, COUNT(*) FROM transactions GROUP BY action"
    ).fetchall())
    _require(counts == ACTION_COUNTS, f"action counts {counts} != {ACTION_COUNTS}")

    ts_span_seconds = _scalar(connection, """
        SELECT CAST(strftime('%s', MAX(ts)) AS INTEGER)
             - CAST(strftime('%s', MIN(ts)) AS INTEGER) FROM transactions
    """)
    _require(
        ts_span_seconds <= BUILD_WINDOW_SECONDS,
        f"ts spans {ts_span_seconds}s, more than the {BUILD_WINDOW_SECONDS}s build window — "
        "the column would now carry ordering the evaluation set assumes it does not",
    )

    restocks_without_price = _scalar(
        connection,
        "SELECT COUNT(*) FROM transactions WHERE action = 'restock' AND unit_price IS NOT NULL",
    )
    _require(
        restocks_without_price == 0,
        f"{restocks_without_price} restock rows carry a unit_price; expected none",
    )


def _check_sign_reversal(connection: sqlite3.Connection) -> None:
    """The whole exercise rests on this: ignoring the sign reverses the ranking."""
    unaware = connection.execute(
        _SALES_BY.format(group_by="color", amount="qty_delta * unit_price")
    ).fetchone()
    aware = connection.execute(
        _SALES_BY.format(group_by="color", amount="ABS(qty_delta) * unit_price")
    ).fetchone()

    _require(
        unaware[0] == SIGN_UNAWARE_TOP_COLOR
        and abs(unaware[1] - SIGN_UNAWARE_TOP_VALUE) < VALUE_TOLERANCE,
        f"sign-unaware top {unaware} != ({SIGN_UNAWARE_TOP_COLOR}, {SIGN_UNAWARE_TOP_VALUE})",
    )
    _require(
        aware[0] == SIGN_AWARE_TOP_COLOR
        and abs(aware[1] - SIGN_AWARE_TOP_VALUE) < VALUE_TOLERANCE,
        f"sign-aware top {aware} != ({SIGN_AWARE_TOP_COLOR}, {SIGN_AWARE_TOP_VALUE})",
    )
    _require(
        unaware[0] != aware[0],
        "the two queries agree on the top colour, so the exercise has no failure to catch",
    )

    unfiltered = _scalar(connection, """
        SELECT SUM(qty_delta * unit_price) AS v FROM transactions
        GROUP BY color ORDER BY v DESC LIMIT 1
    """)
    _require(
        abs(unfiltered - UNFILTERED_TOP_VALUE) < VALUE_TOLERANCE,
        f"unfiltered top {unfiltered} != {UNFILTERED_TOP_VALUE}",
    )


def _check_expectations(connection: sqlite3.Connection) -> None:
    for expectation in EXPECTATIONS:
        row = connection.execute(expectation.reference_sql).fetchone()
        _require(row is not None, f"[{expectation.question}] returned no rows")

        actual_key, actual_value = row
        _require(
            actual_value is not None,
            f"[{expectation.question}] answer is NULL — it cannot score anything",
        )
        _require(
            expectation.key is None or str(actual_key) == expectation.key,
            f"[{expectation.question}] key {actual_key!r} != {expectation.key!r}",
        )
        _require(
            abs(actual_value - expectation.value) < VALUE_TOLERANCE,
            f"[{expectation.question}] value {actual_value} != {expectation.value}",
        )


def compare_with_lab_generator(db_path: Path | str) -> int:
    """Compare every row against the lab generator's output. Returns rows checked.

    The pinned values above would still pass if, say, a `notes` string drifted,
    so this walks all columns. `ts` is excluded: it records when the file was
    built, not anything about the events.

    Raises `FileNotFoundError` if the lab's utils.py is not available.
    """
    if not LAB_UTILS_PATH.exists():
        raise FileNotFoundError(f"lab generator not found at {LAB_UTILS_PATH}")

    spec = importlib.util.spec_from_file_location("lab_utils", LAB_UTILS_PATH)
    lab_utils = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lab_utils)

    with tempfile.TemporaryDirectory() as tmp:
        reference_path = Path(tmp) / "reference.db"
        lab_utils.create_transactions_db(str(reference_path))

        # closing(): sqlite3's own context manager commits the transaction but
        # leaves the connection open, and this one points inside a directory
        # that is about to be removed.
        with closing(sqlite3.connect(reference_path)) as reference, \
                closing(sqlite3.connect(db_path)) as ours:
            columns = [
                row[1] for row in reference.execute("PRAGMA table_info(transactions)")
                if row[1] != GENERATED_AT_COLUMN
            ]
            select = f"SELECT {', '.join(columns)} FROM transactions ORDER BY id"
            reference_rows = reference.execute(select).fetchall()
            our_rows = ours.execute(select).fetchall()

    _require(
        len(reference_rows) == len(our_rows),
        f"row count {len(our_rows)} != lab's {len(reference_rows)}",
    )
    for index, (expected, actual) in enumerate(zip(reference_rows, our_rows), start=1):
        _require(expected == actual, f"row {index} differs\n  lab:  {expected}\n  ours: {actual}")

    return len(our_rows)


# --- main entry point ---


def check_dataset(db_path: Path | str = DEFAULT_DB_PATH) -> None:
    """Raise `InvariantError` unless the database matches every pinned value."""
    with closing(sqlite3.connect(db_path)) as connection:
        _check_shape(connection)
        _check_sign_reversal(connection)
        _check_expectations(connection)


def main() -> None:
    # Rebuild rather than reuse: this is the check that the generator still
    # produces the data everything else is measured against.
    db_path = create_transactions_db()
    check_dataset(db_path)

    print(f"{db_path.name}: {TOTAL_ROWS:,} rows, all invariants hold")
    print(f"  sign-unaware top   {SIGN_UNAWARE_TOP_COLOR:<6} {SIGN_UNAWARE_TOP_VALUE:>12,.2f}")
    print(f"  sign-aware top     {SIGN_AWARE_TOP_COLOR:<6} {SIGN_AWARE_TOP_VALUE:>12,.2f}")
    print(f"  {len(EXPECTATIONS)} evaluation answers verified")

    try:
        checked = compare_with_lab_generator(db_path)
    except FileNotFoundError as error:
        print(f"  lab comparison skipped — {error}")
        return
    print(f"  identical to the lab generator across {checked:,} rows")


if __name__ == "__main__":
    main()
