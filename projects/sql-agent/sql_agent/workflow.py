"""The lab's five-step workflow, run under one of four review conditions.

    schema -> generate V1 -> execute V1 -> review -> execute V2

The lab has one path through this: review with the execution result. The other
three exist to make that path measurable. Without a no-review baseline there is
nothing for the reviewed runs to beat, and without a text-only run there is no
way to say the execution result is what helped.

The fourth is ours. The lab's two review calls differ in more than the feedback
— one runs at temperature 0 and the other at 1.0 — so a difference between them
cannot be attributed to the feedback alone. `feedback-t0` runs the same call at
the text review's temperature and closes that gap. The prompt is untouched;
only the argument changes.

`run_sql_workflow` returns its artifacts rather than only printing them, which
the lab's version does not. Scoring and aggregation both need the objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sql_agent import config, sqlgen
from sql_agent.dataset import DEFAULT_DB_PATH, ensure_database, get_schema
from sql_agent.executor import QueryResult, run_query
from sql_agent.invariants import Expectation
from sql_agent.scoring import Score, score
from sql_agent.sqlgen import Review
from sql_agent.trace import RunTrace

# --- types ---


@dataclass(frozen=True)
class Condition:
    """One way of reviewing the first query — or not reviewing it."""

    name: str
    uses_execution_output: bool
    temperature: float | None
    description: str

    @property
    def has_review(self) -> bool:
        return self.temperature is not None


@dataclass(frozen=True)
class WorkflowResult:
    """Everything one run produced."""

    question: str
    condition: str
    schema: str
    sql_v1: str
    result_v1: QueryResult
    review: Review | None = None
    sql_v2: str | None = None
    result_v2: QueryResult | None = None
    score: Score | None = None

    @property
    def final_sql(self) -> str:
        return self.sql_v2 if self.sql_v2 is not None else self.sql_v1

    @property
    def final_result(self) -> QueryResult:
        """What the workflow would present as its answer."""
        return self.result_v2 if self.result_v2 is not None else self.result_v1

    @property
    def is_correct(self) -> bool:
        """False when nothing was scored — an unscored run has not been shown correct."""
        return self.score is not None and self.score.is_correct


# --- constants ---

NO_REVIEW = Condition(
    "none", uses_execution_output=False, temperature=None,
    description="baseline — the first query is the answer",
)
TEXT_ONLY = Condition(
    "text", uses_execution_output=False, temperature=config.TEXT_REVIEW_TEMPERATURE,
    description="the lab's 3.2.1 — review the SQL text",
)
WITH_OUTPUT = Condition(
    "feedback", uses_execution_output=True, temperature=config.EXTERNAL_FEEDBACK_TEMPERATURE,
    description="the lab's 3.2.2 — review the SQL and its result",
)
WITH_OUTPUT_CONTROLLED = Condition(
    "feedback-t0", uses_execution_output=True,
    temperature=config.CONTROLLED_FEEDBACK_TEMPERATURE,
    description="as above at the text review's temperature, isolating the feedback",
)

CONDITIONS = {c.name: c for c in (NO_REVIEW, TEXT_ONLY, WITH_OUTPUT, WITH_OUTPUT_CONTROLLED)}
DEFAULT_CONDITION = WITH_OUTPUT.name


# --- helpers ---


def _review_for(condition: Condition, question: str, sql_v1: str, result_v1: QueryResult,
                schema: str, model: str) -> Review:
    """Run the review this condition calls for."""
    if condition.uses_execution_output:
        return sqlgen.refine_sql_external_feedback(
            question, sql_v1, result_v1.to_markdown(), schema,
            model=model, temperature=condition.temperature,
        )
    return sqlgen.refine_sql(
        question, sql_v1, schema, model=model, temperature=condition.temperature,
    )


# --- main export ---


def resolve_condition(name: str) -> Condition:
    """Look up a condition by name.

    Raises:
        ValueError: no such condition, listing the ones that exist.
    """
    if name not in CONDITIONS:
        known = ", ".join(CONDITIONS)
        raise ValueError(f"unknown condition {name!r}. Known: {known}.")
    return CONDITIONS[name]


def run_sql_workflow(
    question: str,
    condition: str = DEFAULT_CONDITION,
    db_path: Path | str = DEFAULT_DB_PATH,
    generation_model: str = config.DEFAULT_GENERATION_MODEL,
    evaluation_model: str = config.DEFAULT_EVALUATION_MODEL,
    expectation: Expectation | None = None,
    trace: RunTrace | None = None,
    sql_v1: str | None = None,
) -> WorkflowResult:
    """Answer `question` under `condition`, scoring the result if an answer is known.

    Pass `sql_v1` to skip generation and review a query that is already written.
    Comparing reviewers needs that: generated queries differ between models, so
    without a fixed one a weaker score could mean the reviewer missed the flaw
    or that it was handed a different flaw to begin with.

    Verifies prompt fidelity before the first model call. A batch is hundreds of
    calls and the prompts are what every difference is attributed to, so finding
    out afterwards that one had drifted would waste the whole run.
    """
    chosen = resolve_condition(condition)
    sqlgen.check_prompts()
    db_path = ensure_database(db_path)

    trace = trace or RunTrace(question, chosen.name, generation_model, evaluation_model)

    with trace.timed("schema"):
        schema = get_schema(db_path)

    is_v1_supplied = sql_v1 is not None
    with trace.timed("generate_v1", None if is_v1_supplied else generation_model) as step:
        if not is_v1_supplied:
            sql_v1 = sqlgen.generate_sql(question, schema, model=generation_model)
        step.detail = {"sql": sql_v1, "reused": is_v1_supplied}

    with trace.timed("execute_v1") as step:
        result_v1 = run_query(sql_v1, db_path)
        step.detail = {"has_error": result_v1.has_error, "rows": result_v1.row_count}

    if not chosen.has_review:
        return _finish(
            question, chosen, schema, sql_v1, result_v1,
            expectation=expectation, trace=trace,
        )

    with trace.timed("review", evaluation_model) as step:
        review = _review_for(chosen, question, sql_v1, result_v1, schema, evaluation_model)
        step.detail = {
            "temperature": chosen.temperature,
            "sees_execution_output": chosen.uses_execution_output,
            "is_json_parsed": review.is_json_parsed,
            "changed_sql": review.refined_sql.strip() != sql_v1.strip(),
        }

    with trace.timed("execute_v2") as step:
        result_v2 = run_query(review.refined_sql, db_path)
        step.detail = {"has_error": result_v2.has_error, "rows": result_v2.row_count}

    return _finish(
        question, chosen, schema, sql_v1, result_v1,
        review=review, result_v2=result_v2, expectation=expectation, trace=trace,
    )


def _finish(
    question: str,
    condition: Condition,
    schema: str,
    sql_v1: str,
    result_v1: QueryResult,
    review: Review | None = None,
    result_v2: QueryResult | None = None,
    expectation: Expectation | None = None,
    trace: RunTrace | None = None,
) -> WorkflowResult:
    """Score against a known answer, if there is one, and assemble the result."""
    final_result = result_v2 if result_v2 is not None else result_v1

    verdict = None
    if expectation is not None:
        verdict = score(final_result, expectation)
        if trace is not None:
            with trace.timed("score") as step:
                step.detail = {
                    "is_correct": verdict.is_correct,
                    "reason": verdict.reason,
                    "value_delta": verdict.value_delta,
                }

    return WorkflowResult(
        question=question,
        condition=condition.name,
        schema=schema,
        sql_v1=sql_v1,
        result_v1=result_v1,
        review=review,
        sql_v2=review.refined_sql if review is not None else None,
        result_v2=result_v2,
        score=verdict,
    )
