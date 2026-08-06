"""Decide whether a query reached the known answer.

Success rates are the whole output of this project, so what counts as success
has to be written down rather than eyeballed. The rule is the one a person
would apply when grading: look at the first row, and check it carries the right
label and the right number.

Column names and order are ignored. `SELECT color, SUM(ABS(qty_delta)*unit_price)`
and `SELECT color AS c, SUM(-qty_delta*unit_price) AS revenue` are the same
answer, and so is any other spelling that lands on the same row — comparing SQL
text would score phrasing instead of correctness.

Ordering is not ignored. A question like "which colour is highest" is only
answered if the model put that colour first; returning all five unsorted is
leaving the choice to the reader.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from sql_agent.executor import QueryResult
from sql_agent.invariants import VALUE_TOLERANCE, Expectation

# --- types ---


@dataclass(frozen=True)
class Score:
    """Whether one query answered its question, and why.

    `value_delta` is kept even on a pass so near-misses stay visible in a batch
    — a run that fails by 0.09 is a different story from one that returns the
    wrong colour, and only the number tells them apart.
    """

    is_correct: bool
    reason: str
    actual_key: str | None = None
    actual_value: float | None = None
    value_delta: float | None = None


# --- constants ---

# Why a row failed, in the order the checks run.
REASON_EXECUTION_ERROR = "query failed to execute"
REASON_NO_ROWS = "query returned no rows"
REASON_KEY_MISMATCH = "expected key not in the first row"
REASON_VALUE_MISMATCH = "expected value not in the first row"
REASON_CORRECT = "first row carries the expected answer"


# --- helpers ---


def _as_number(cell) -> float | None:
    """The cell as a float, or None if it is not a number.

    Booleans are excluded: SQLite returns them as 0/1 and a boolean column
    would otherwise stand in for a count of zero or one.
    """
    if isinstance(cell, bool) or cell is None or pd.isna(cell):
        return None
    try:
        return float(cell)
    except (TypeError, ValueError):
        return None


def _find_key(row: pd.Series, expected_key: str) -> str | None:
    """The cell matching `expected_key`, compared as text.

    Text comparison so a model returning 34 and one returning "34" both match;
    the DataFrame's dtype is an artefact of the query, not part of the answer.
    """
    for cell in row:
        if cell is not None and not pd.isna(cell) and str(cell).strip() == expected_key:
            return str(cell)
    return None


def _find_value(row: pd.Series, expected_value: float) -> tuple[float | None, float | None]:
    """The numeric cell closest to `expected_value`, and its distance.

    Returns the closest rather than the first match so the delta is meaningful
    when nothing is within tolerance — that is what turns "wrong" into "wrong
    by how much".
    """
    numbers = [n for n in (_as_number(cell) for cell in row) if n is not None]
    if not numbers:
        return None, None

    closest = min(numbers, key=lambda n: abs(n - expected_value))
    return closest, abs(closest - expected_value)


# --- main export ---


def score(result: QueryResult, expectation: Expectation) -> Score:
    """Grade one query result against its known answer.

    The checks run in order, and the first failure is the reason: an error
    frame is not a wrong answer, and an empty result is not a wrong number.
    Collapsing them would hide which part of the workflow broke.
    """
    if result.has_error:
        return Score(False, REASON_EXECUTION_ERROR)

    if result.frame.empty:
        return Score(False, REASON_NO_ROWS)

    first_row = result.frame.iloc[0]

    actual_key = None
    if expectation.key is not None:
        actual_key = _find_key(first_row, expectation.key)
        if actual_key is None:
            return Score(False, REASON_KEY_MISMATCH)

    actual_value, delta = _find_value(first_row, expectation.value)
    if delta is None or delta > VALUE_TOLERANCE:
        return Score(False, REASON_VALUE_MISMATCH, actual_key, actual_value, delta)

    return Score(True, REASON_CORRECT, actual_key, actual_value, delta)
