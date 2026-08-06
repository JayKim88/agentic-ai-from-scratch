"""Run model-written SQL against the transactions database.

The lab's `execute_sql` turns any failure into a one-row DataFrame with an
`error` column, and that frame is what gets rendered into the review prompt.
So a failed query is not a dead end here — the error message *is* the external
feedback the model reflects on. That behaviour is kept exactly.

What is added is a way to tell the two apart. The lab's caller cannot: a result
frame and an error frame are both just DataFrames, so an error can be displayed
as the workflow's final answer. `QueryResult.has_error` makes it explicit, which
the scorer needs — an error frame must never count as reaching the answer.

Two safeguards the lab does not need but a batch run does:

  - the connection is read-only, so a generated DROP or UPDATE cannot damage
    the database that every measurement depends on. This does change what the
    model sees: in the lab a DROP would succeed;
  - queries are interrupted past a deadline, so one cartesian join cannot stall
    a run of hundreds of queries.

Both surface as ordinary error frames, which means the model sees them as
feedback like any other failure.
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from sql_agent.dataset import DEFAULT_DB_PATH

# --- types ---


@dataclass(frozen=True)
class QueryResult:
    """Outcome of one query.

    `frame` is exactly what the lab's `execute_sql` would return, error frames
    included, because it is what goes into the review prompt.
    """

    sql: str
    frame: pd.DataFrame
    error: str | None = None

    @property
    def has_error(self) -> bool:
        return self.error is not None

    @property
    def row_count(self) -> int:
        """Rows in `frame`. An error frame holds one — check `has_error` first."""
        return len(self.frame)

    def to_markdown(self) -> str:
        """Render for the review prompt, the way the lab does."""
        return self.frame.to_markdown(index=False)


# --- constants ---

ERROR_COLUMN = "error"

# The lab strips exactly these two, nothing more. Reproduced rather than
# improved: a looser strip would rescue queries that fail in the lab, and the
# success rates would then describe our normalisation instead of the model.
SQL_FENCE_PREFIX = "```sql"
SQL_FENCE_SUFFIX = "```"

DEFAULT_TIMEOUT_SECONDS = 10.0

# How many VM instructions SQLite runs between deadline checks. Small enough to
# interrupt promptly, large enough that the check costs nothing on real queries.
PROGRESS_HANDLER_INSTRUCTIONS = 10_000

# --- helpers ---


class _Deadline:
    """Progress handler that aborts a statement once its time is up.

    Records the fact separately: pandas wraps the sqlite3 error in its own
    exception type, so neither `isinstance` nor the message reliably says
    whether the abort came from this deadline.
    """

    def __init__(self, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds
        self.has_expired = False
        self._expires_at = time.monotonic() + timeout_seconds

    def __call__(self) -> int:
        # A non-zero return aborts the running statement.
        if time.monotonic() <= self._expires_at:
            return 0
        self.has_expired = True
        return 1


def _strip_markdown_fence(sql: str) -> str:
    """Remove the fence a model may wrap its SQL in, exactly as the lab does."""
    return sql.strip().removeprefix(SQL_FENCE_PREFIX).removesuffix(SQL_FENCE_SUFFIX).strip()


def _error_frame(message: str) -> pd.DataFrame:
    return pd.DataFrame({ERROR_COLUMN: [message]})


def _open_readonly(db_path: Path) -> sqlite3.Connection:
    """Open the database read-only.

    A missing file would otherwise be created empty and every query would fail
    with a confusing "no such table", so the absence is reported as itself.

    `as_uri()` rather than an f-string: a path holding "?" or "#" would end up
    parsed as the URI's query or fragment, SQLite would open some other file,
    and the resulting "no such table" would look like the model's mistake.
    """
    if not db_path.exists():
        raise FileNotFoundError(f"database not found: {db_path}")
    return sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)


def _enforce_deadline(connection: sqlite3.Connection, timeout_seconds: float) -> _Deadline:
    """Interrupt any statement still running past `timeout_seconds`."""
    deadline = _Deadline(timeout_seconds)
    connection.set_progress_handler(deadline, PROGRESS_HANDLER_INSTRUCTIONS)
    return deadline


# --- main entry point ---


def run_query(
    sql: str,
    db_path: Path | str = DEFAULT_DB_PATH,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> QueryResult:
    """Execute `sql` read-only and return the result, errors included.

    Never raises for a bad query: a syntax error, a write attempt and a timeout
    all come back as `QueryResult` with `has_error` set and an error frame ready
    to be shown to the model. Only a missing database file raises, since that is
    a setup problem rather than something reflection can fix.
    """
    statement = _strip_markdown_fence(sql)

    with closing(_open_readonly(Path(db_path))) as connection:
        deadline = _enforce_deadline(connection, timeout_seconds)
        try:
            frame = pd.read_sql_query(statement, connection)
        except Exception as error:  # noqa: BLE001 — the message is the feedback
            message = (
                f"query exceeded the {timeout_seconds:g}s limit and was interrupted"
                if deadline.has_expired
                else str(error)
            )
            return QueryResult(statement, _error_frame(message), error=message)

    return QueryResult(statement, frame)
