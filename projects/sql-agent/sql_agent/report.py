"""Show each step, and keep it on disk.

The lab renders every step into the notebook with `print_html`, and says why:
the learner is meant to watch the query change rather than only see the final
table. That intent is kept — the HTML is not, since this runs in a terminal.

One thing is deliberately not copied. The lab writes its verdict into the
heading it prints:

    print_html(df_v2, title="SQL Output of V2 - ❌ Does NOT fully answer the question")

Nothing is checked there; the mark is a fixed string. Here the verdict comes
from `scoring`, which looks at the values, so a run that happens to succeed is
never labelled a failure and the reverse cannot happen either.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from sql_agent import config
from sql_agent.trace import RunTrace
from sql_agent.workflow import WorkflowResult

# --- constants ---

SEPARATOR_WIDTH = 78
TRACE_FILENAME = "trace.json"
RESULT_FILENAME = "result.json"

CORRECT_MARK = "PASS"
INCORRECT_MARK = "FAIL"
UNSCORED_MARK = "not scored"


# --- helpers ---


def _heading(title: str) -> str:
    return f"\n{title}\n{'-' * SEPARATOR_WIDTH}"


def _indented(text: str) -> str:
    return "\n".join(f"  {line}" for line in (text or "").splitlines())


def _verdict_of(result: WorkflowResult) -> str:
    if result.score is None:
        return UNSCORED_MARK
    mark = CORRECT_MARK if result.score.is_correct else INCORRECT_MARK
    return f"{mark} — {result.score.reason}"


def _as_dict(result: WorkflowResult) -> dict:
    """The run as plain data, for the run directory."""
    return {
        "question": result.question,
        "condition": result.condition,
        "sql_v1": result.sql_v1,
        "result_v1": result.result_v1.to_markdown(),
        "v1_has_error": result.result_v1.has_error,
        "feedback": result.review.feedback if result.review else None,
        "is_json_parsed": result.review.is_json_parsed if result.review else None,
        "sql_v2": result.sql_v2,
        "result_v2": result.result_v2.to_markdown() if result.result_v2 else None,
        "v2_has_error": result.result_v2.has_error if result.result_v2 else None,
        "is_correct": result.is_correct,
        "score_reason": result.score.reason if result.score else None,
        "value_delta": result.score.value_delta if result.score else None,
    }


# --- main export ---


def new_run_directory(label: str = config.DEFAULT_RUN_LABEL) -> Path:
    """A fresh directory for this batch, named for when it started."""
    stamp = datetime.now().strftime(config.RUN_DIRECTORY_FORMAT)
    path = config.RUNS_DIR / f"{stamp}_{label}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def iteration_directory(run_directory: Path, condition: str, iteration: int) -> Path:
    """Where one run of one condition keeps its files.

    Conditions and iterations nest so that a batch of dozens stays readable and
    two runs of the same condition never overwrite each other.
    """
    path = run_directory / condition / f"{iteration:02d}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def show(result: WorkflowResult, show_schema: bool = False) -> None:
    """Print the run the way the lab walks through it, step by step."""
    print(_heading(f"Question ({result.condition})"))
    print(_indented(result.question))

    if show_schema:
        print(_heading("Step 1 — schema, as the model receives it"))
        print(_indented(result.schema))

    print(_heading("Step 2 — SQL V1"))
    print(_indented(result.sql_v1))

    print(_heading("Step 3 — V1 output"))
    print(_indented(result.result_v1.to_markdown()))

    if result.review is not None:
        parsed = "" if result.review.is_json_parsed else "  [reply was not valid JSON]"
        print(_heading(f"Step 4 — review{parsed}"))
        print(_indented(result.review.feedback))

        print(_heading("Step 4 — SQL V2"))
        print(_indented(result.sql_v2))

        print(_heading("Step 5 — V2 output"))
        print(_indented(result.result_v2.to_markdown()))

    print(_heading("Verdict"))
    print(_indented(_verdict_of(result)))


def save(result: WorkflowResult, trace: RunTrace, directory: Path) -> Path:
    """Write the run's artifacts and trace into `directory`."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / RESULT_FILENAME).write_text(
        json.dumps(_as_dict(result), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    trace.save(directory / TRACE_FILENAME)
    return directory
