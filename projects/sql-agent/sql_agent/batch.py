"""Repeat runs and count how often each one reached the answer.

A single run says nothing on its own — the lab notes that LLMs are stochastic,
and a wrong answer could be the condition or could be the draw. What is being
checked is the direction between conditions, not any one outcome.

How many repeats each condition gets is deliberately uneven. Three of the four
run at temperature 0 and are close to deterministic, so ten repeats of those
would be the same answer ten times; the money goes to the one that actually
varies. If a temperature-0 condition does split across its repeats, that is
worth knowing on its own and shows up here.

Model comparison holds V1 fixed. Reviewers are compared on the same query and
the same execution output, so a difference is the reviewer's — otherwise a
weaker score could mean it was handed a different flaw to begin with. The lab's
claim is about reviewing ("best results for self-reflection tasks"), so this is
what it actually says.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from sql_agent import config, report, sqlgen
from sql_agent.dataset import DEFAULT_DB_PATH, ensure_database, get_schema
from sql_agent.executor import QueryResult, run_query
from sql_agent.invariants import Expectation
from sql_agent.scoring import score
from sql_agent.sqlgen import REFINED_SQL_KEY
from sql_agent.trace import RunTrace
from sql_agent.workflow import CONDITIONS, WorkflowResult, run_sql_workflow

# --- types ---


@dataclass(frozen=True)
class Outcome:
    """One run's verdict, flattened for counting."""

    iteration: int
    is_correct: bool
    reason: str
    value_delta: float | None = None
    changed_sql: bool | None = None
    is_json_parsed: bool | None = None


@dataclass
class Tally:
    """Every run under one label — a condition, or a reviewing model."""

    label: str
    detail: str = ""
    outcomes: list[Outcome] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.outcomes)

    @property
    def passed(self) -> int:
        return sum(outcome.is_correct for outcome in self.outcomes)

    @property
    def rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    @property
    def is_unanimous(self) -> bool:
        """Whether every repeat agreed. A split at temperature 0 is worth noticing."""
        return self.passed in (0, self.total)

    @property
    def unparsed(self) -> int:
        """Repeats whose review did not come back as JSON.

        Surfaced next to the pass rate because it is a different kind of
        failure: the model may have found the flaw and fixed it, and only the
        wrapping stopped the answer being read. Counting those as "could not
        reflect" would be reading the wrong thing out of the number.
        """
        return sum(outcome.is_json_parsed is False for outcome in self.outcomes)


# --- constants ---

# Temperature-0 conditions get fewer repeats: they are close to deterministic,
# so the extra calls would buy the same answer again.
REPEATS_BY_CONDITION = {
    "none": 5,
    "text": 5,
    "feedback": 10,
    "feedback-t0": 5,
}

MODEL_COMPARISON_REPEATS = 3
MODEL_COMPARISON_CONDITION = "feedback"

# The four the lab offers for its model-comparison exercise.
LAB_MODELS = (
    "openai:gpt-4.1",
    "openai:gpt-4o",
    "openai:gpt-4.1-mini",
    "openai:gpt-3.5-turbo",
)

SUMMARY_FILENAME = "summary.json"

# What a fenced review reply is wrapped in. Only used to measure the cost of the
# lab not stripping it — `_parse_review` is left reproducing the lab exactly.
REVIEW_FENCE_PREFIX = "```json"
REVIEW_FENCE_SUFFIX = "```"


# --- helpers ---


def _outcome_of(result: WorkflowResult, iteration: int) -> Outcome:
    review = result.review
    return Outcome(
        iteration=iteration,
        is_correct=result.is_correct,
        reason=result.score.reason if result.score else "not scored",
        value_delta=result.score.value_delta if result.score else None,
        changed_sql=None if review is None else review.refined_sql.strip() != result.sql_v1.strip(),
        is_json_parsed=None if review is None else review.is_json_parsed,
    )


def _run_once(
    expectation: Expectation,
    condition: str,
    iteration: int,
    run_directory: Path,
    subdirectory: str,
    generation_model: str,
    evaluation_model: str,
    db_path: Path,
    sql_v1: str | None,
) -> Outcome:
    trace = RunTrace(expectation.question, condition, generation_model, evaluation_model)
    result = run_sql_workflow(
        expectation.question,
        condition=condition,
        db_path=db_path,
        generation_model=generation_model,
        evaluation_model=evaluation_model,
        expectation=expectation,
        trace=trace,
        sql_v1=sql_v1,
    )
    report.save(result, trace, report.iteration_directory(run_directory, subdirectory, iteration))
    return _outcome_of(result, iteration)


def _summary_payload(question: str, tallies: list[Tally], note: str) -> dict:
    return {
        "question": question,
        "note": note,
        "tallies": [
            {
                "label": tally.label,
                "detail": tally.detail,
                "passed": tally.passed,
                "total": tally.total,
                "rate": round(tally.rate, 3),
                "unanimous": tally.is_unanimous,
                "outcomes": [asdict(outcome) for outcome in tally.outcomes],
            }
            for tally in tallies
        ],
    }


# --- main export ---


def run_conditions(
    expectation: Expectation,
    run_directory: Path,
    repeats: dict[str, int] | None = None,
    db_path: Path | str = DEFAULT_DB_PATH,
    generation_model: str = config.DEFAULT_GENERATION_MODEL,
    evaluation_model: str = config.DEFAULT_EVALUATION_MODEL,
    on_progress=None,
) -> list[Tally]:
    """Run every condition its own number of times and count the passes."""
    repeats = repeats or REPEATS_BY_CONDITION
    db_path = ensure_database(db_path)

    tallies = []
    for name, condition in CONDITIONS.items():
        tally = Tally(name, condition.description)
        for iteration in range(1, repeats.get(name, 1) + 1):
            outcome = _run_once(
                expectation, name, iteration, run_directory, name,
                generation_model, evaluation_model, db_path, sql_v1=None,
            )
            tally.outcomes.append(outcome)
            if on_progress:
                on_progress(name, iteration, outcome)
        tallies.append(tally)

    return tallies


def run_model_comparison(
    expectation: Expectation,
    run_directory: Path,
    models: tuple[str, ...] = LAB_MODELS,
    repeats: int = MODEL_COMPARISON_REPEATS,
    db_path: Path | str = DEFAULT_DB_PATH,
    generation_model: str = config.DEFAULT_GENERATION_MODEL,
    on_progress=None,
) -> tuple[str, list[Tally], QueryResult]:
    """Give every model the same query to review.

    Returns the fixed V1, the tallies, and V1's execution result — the last so a
    report can show what every reviewer was looking at.
    """
    db_path = ensure_database(db_path)
    sqlgen.check_prompts()

    schema = get_schema(db_path)
    fixed_sql_v1 = sqlgen.generate_sql(expectation.question, schema, model=generation_model)
    baseline = run_query(fixed_sql_v1, db_path)

    tallies = []
    for model in models:
        tally = Tally(model, f"reviewing a fixed V1 ({MODEL_COMPARISON_CONDITION})")
        for iteration in range(1, repeats + 1):
            outcome = _run_once(
                expectation, MODEL_COMPARISON_CONDITION, iteration, run_directory,
                f"model_{model.split(config.PROVIDER_SEPARATOR)[-1]}",
                generation_model, model, db_path, sql_v1=fixed_sql_v1,
            )
            tally.outcomes.append(outcome)
            if on_progress:
                on_progress(model, iteration, outcome)
        tallies.append(tally)

    return fixed_sql_v1, tallies, baseline


def save_summary(
    question: str, tallies: list[Tally], run_directory: Path, note: str = "", name: str = SUMMARY_FILENAME
) -> Path:
    """Write the counts beside the individual runs."""
    path = run_directory / name
    path.write_text(
        json.dumps(_summary_payload(question, tallies, note), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def format_table(tallies: list[Tally], heading: str) -> str:
    """The counts as a table.

    Unparsed replies get their own note. A row reading 0/3 means something
    different when all three failed to parse, and the table has to say so
    without the reader opening the saved runs.
    """
    width = max(len(tally.label) for tally in tallies)
    lines = [heading, "-" * 78]
    for tally in tallies:
        bar = "".join("#" if outcome.is_correct else "." for outcome in tally.outcomes)
        notes = []
        if not tally.is_unanimous:
            notes.append("split")
        if tally.unparsed:
            notes.append(f"{tally.unparsed}/{tally.total} replies were not JSON")
        note = f"   <- {'; '.join(notes)}" if notes else ""
        lines.append(
            f"  {tally.label:<{width}}  {tally.passed:>2}/{tally.total:<2} "
            f"{tally.rate:>5.0%}  {bar}{note}"
        )
    return "\n".join(lines)


def rescore_without_fences(
    run_directory: Path, expectation: Expectation, db_path: Path | str = DEFAULT_DB_PATH
) -> dict[str, tuple[int, int]]:
    """Re-score saved runs whose review arrived wrapped in a markdown fence.

    Reads replies already on disk — no model is called. `_parse_review`
    reproduces the lab, which strips a fence off generated SQL but not off a
    review, so a correctly reasoned reply that came back fenced is scored as a
    failure. This says how many of those there were.

    Returns {label: (as the lab scores it, with the fence removed)}.
    """
    results: dict[str, tuple[int, int]] = {}

    for subdirectory in sorted(p for p in run_directory.iterdir() if p.is_dir()):
        as_scored = rescored = 0
        for path in sorted(subdirectory.glob(f"*/{report.RESULT_FILENAME}")):
            saved = json.loads(path.read_text())
            as_scored += bool(saved["is_correct"])

            if saved["is_json_parsed"] is not False:
                rescored += bool(saved["is_correct"])
                continue

            body = saved["feedback"].strip()
            body = body.removeprefix(REVIEW_FENCE_PREFIX).removesuffix(REVIEW_FENCE_SUFFIX).strip()
            try:
                refined = json.loads(body).get(REFINED_SQL_KEY, "")
            except json.JSONDecodeError:
                continue
            rescored += score(run_query(refined, db_path), expectation).is_correct

        results[subdirectory.name] = (as_scored, rescored)

    return results
