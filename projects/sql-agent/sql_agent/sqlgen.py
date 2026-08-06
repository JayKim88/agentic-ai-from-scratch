"""The lab's three model calls: write SQL, review it, review it with the result.

The prompt templates below are the lab's, reproduced to the byte — leading
newline and trailing indentation included, since those go to the model too.
They are what every measured difference is attributed to, so a "tidier" prompt
would quietly make this project measure something else. `check_prompts()`
renders ours and the lab's side by side and refuses to pass on a mismatch.

Two review functions, and the difference between them is the point of the lab:

    refine_sql                     sees the SQL text only
    refine_sql_external_feedback   sees the SQL and what it returned

They differ in more than that, though — the lab runs the first at temperature 0
and the second at 1.0. `temperature` is therefore a parameter here rather than
a literal, so the second can also be run at 0 and the execution result left as
the only difference (config.CONTROLLED_FEEDBACK_TEMPERATURE).

Run directly to verify prompt fidelity:

    python -m sql_agent.sqlgen
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from sql_agent import config, llm

# --- types ---


@dataclass(frozen=True)
class Review:
    """One review turn: what the model said, and the SQL it wants run next.

    `is_json_parsed` records whether the reply was valid JSON. The lab's
    fallback puts the raw reply into `feedback` and keeps the original SQL,
    which reads exactly like a review that found nothing wrong — so without
    this flag a parsing failure is indistinguishable from a clean pass.
    """

    feedback: str
    refined_sql: str
    is_json_parsed: bool


# --- constants ---

FEEDBACK_KEY = "feedback"
REFINED_SQL_KEY = "refined_sql"

# The lab's notebook, used by `check_prompts()` to compare against.
LAB_NOTEBOOK_PATH = (
    Path(__file__).resolve().parents[3] / "labs" / "module-2" / "sql" / "M2_UGL_2.md"
)
_LAB_PROMPT_PATTERN = re.compile(r'prompt = f"""(.*?)"""', re.S)
LAB_PROMPT_NAMES = ("generate_sql", "refine_sql", "refine_sql_external_feedback")

# The one placeholder the lab writes as an expression. str.format cannot call a
# method, so it is swapped for a plain field that receives the rendered table.
_LAB_TABLE_EXPRESSION = "{df_feedback.to_markdown(index=False)}"

GENERATE_SQL_PROMPT = """
    You are a SQL assistant. Given the schema and the user's question, write a SQL query for SQLite.

    Schema:
    {schema}

    User question:
    {question}

    Respond with the SQL only.
    """

# Note the missing indentation: the lab writes this one flush left while the
# other two are indented four spaces. Kept as it is.
REFINE_SQL_PROMPT = """
You are a SQL reviewer and refiner.

User asked:
{question}

Original SQL:
{sql_query}

Table Schema:
{schema}

Step 1: Briefly evaluate if the SQL OUTPUT fully answers the user's question.
Step 2: If improvement is needed, provide a refined SQL query for SQLite.
If the original SQL is already correct, return it unchanged.

Return STRICT JSON with two fields:
{{
  "feedback": "<1-3 sentences explaining the gap or confirming correctness>",
  "refined_sql": "<final SQL to run>"
}}
"""

# The lab interpolates `df_feedback.to_markdown(index=False)` here. This takes
# the rendered table instead — an expression cannot go through str.format —
# which produces the identical prompt.
REFINE_SQL_EXTERNAL_FEEDBACK_PROMPT = """
    You are a SQL reviewer and refiner.

    User asked:
    {question}

    Original SQL:
    {sql_query}

    SQL Output:
    {sql_output}

    Table Schema:
    {schema}

    Step 1: Briefly evaluate if the SQL output answers the user's question.
    Step 2: If the SQL could be improved, provide a refined SQL query.
    If the original SQL is already correct, return it unchanged.

    Return a strict JSON object with two fields:
    - "feedback": brief evaluation and suggestions
    - "refined_sql": the final SQL to run
    """


# --- helpers ---


def _parse_review(reply: str, original_sql: str) -> Review:
    """Read `{"feedback", "refined_sql"}` out of a reply, falling back as the lab does.

    On a parsing failure the raw reply becomes the feedback and the original SQL
    is kept, so the workflow still moves — but `is_json_parsed` says what
    happened rather than letting it look like a review that approved the query.
    """
    try:
        parsed = json.loads(reply)
    except (json.JSONDecodeError, TypeError):
        return Review(reply.strip(), original_sql, is_json_parsed=False)

    if not isinstance(parsed, dict):
        return Review(reply.strip(), original_sql, is_json_parsed=False)

    feedback = str(parsed.get(FEEDBACK_KEY, "")).strip()
    refined_sql = str(parsed.get(REFINED_SQL_KEY, original_sql)).strip()
    return Review(feedback, refined_sql or original_sql, is_json_parsed=True)


def _render_lab_prompts(question: str, sql_query: str, schema: str, sql_output: str) -> list[str]:
    """Render the notebook's own prompt strings, for comparison.

    The f-string bodies are lifted from the notebook and filled with the same
    values, so what comes back is what the lab would actually send. `str.format`
    rather than `eval`: both treat `{{` and `}}` identically, and there is no
    reason to execute text read off a file.

    Raises:
        AssertionError: the notebook holds a different number of prompts than
            expected, which would make the comparison pair the wrong ones.
    """
    if not LAB_NOTEBOOK_PATH.exists():
        raise FileNotFoundError(f"lab notebook not found at {LAB_NOTEBOOK_PATH}")

    bodies = _LAB_PROMPT_PATTERN.findall(LAB_NOTEBOOK_PATH.read_text())
    if len(bodies) != len(LAB_PROMPT_NAMES):
        raise AssertionError(
            f"expected {len(LAB_PROMPT_NAMES)} prompts in {LAB_NOTEBOOK_PATH.name}, "
            f"found {len(bodies)} — the comparison below would pair the wrong ones"
        )

    return [
        body.replace(_LAB_TABLE_EXPRESSION, "{sql_output}").format(
            question=question, sql_query=sql_query, schema=schema, sql_output=sql_output
        )
        for body in bodies
    ]


# --- main export ---


def generate_sql(question: str, schema: str, model: str = config.DEFAULT_GENERATION_MODEL) -> str:
    """Write a first query for `question`. The lab's step 2."""
    prompt = GENERATE_SQL_PROMPT.format(schema=schema, question=question)
    return llm.complete(model, prompt, config.GENERATION_TEMPERATURE).strip()


def refine_sql(
    question: str,
    sql_query: str,
    schema: str,
    model: str = config.DEFAULT_EVALUATION_MODEL,
    temperature: float = config.TEXT_REVIEW_TEMPERATURE,
) -> Review:
    """Review the query as text, without running it. The lab's 3.2.1.

    The prompt asks the model to evaluate "the SQL OUTPUT" while giving it no
    output — that is the condition being tested, not an oversight to correct.
    """
    prompt = REFINE_SQL_PROMPT.format(question=question, sql_query=sql_query, schema=schema)
    return _parse_review(llm.complete(model, prompt, temperature), sql_query)


def refine_sql_external_feedback(
    question: str,
    sql_query: str,
    sql_output: str,
    schema: str,
    model: str = config.DEFAULT_EVALUATION_MODEL,
    temperature: float = config.EXTERNAL_FEEDBACK_TEMPERATURE,
) -> Review:
    """Review the query together with what it returned. The lab's 3.2.2.

    `sql_output` is the result rendered as markdown — an error table included,
    which is how a failed query still produces feedback to reflect on.
    """
    prompt = REFINE_SQL_EXTERNAL_FEEDBACK_PROMPT.format(
        question=question, sql_query=sql_query, sql_output=sql_output, schema=schema
    )
    return _parse_review(llm.complete(model, prompt, temperature), sql_query)


def check_prompts() -> int:
    """Compare our rendered prompts with the lab's. Returns how many matched.

    Raises:
        AssertionError: a prompt differs from the lab's, with the first
            differing line shown.
        FileNotFoundError: the lab notebook is not available.
    """
    question, sql_query = "Which color?", "SELECT 1"
    schema, sql_output = "table name: transactions\nid (INTEGER)", "| v |\n|--:|\n| 1 |"

    ours = [
        GENERATE_SQL_PROMPT.format(schema=schema, question=question),
        REFINE_SQL_PROMPT.format(question=question, sql_query=sql_query, schema=schema),
        REFINE_SQL_EXTERNAL_FEEDBACK_PROMPT.format(
            question=question, sql_query=sql_query, sql_output=sql_output, schema=schema
        ),
    ]
    theirs = _render_lab_prompts(question, sql_query, schema, sql_output)

    for name, mine, lab_prompt in zip(LAB_PROMPT_NAMES, ours, theirs):
        if mine == lab_prompt:
            continue
        for number, (a, b) in enumerate(zip(lab_prompt.splitlines(), mine.splitlines()), 1):
            if a != b:
                raise AssertionError(
                    f"{name} differs at line {number}\n  lab:  {a!r}\n  ours: {b!r}"
                )
        raise AssertionError(f"{name} differs in length: lab {len(lab_prompt)}, ours {len(mine)}")

    return len(ours)


def main() -> None:
    matched = check_prompts()
    print(f"{matched} prompts match the lab byte for byte, whitespace included")


if __name__ == "__main__":
    main()
