"""Show the chart to a model, get a critique and revised code back (lab step 3).

One call does both jobs. The lab's `reflect_on_image_and_regenerate` returns
`(feedback, refined_code)` from a single response — first line a JSON object,
then the code in `<execute_python>` tags — and parsing that shape is part of
what the lab teaches. Splitting critique from revision is deferred to B4 and
offered as a flag, never as the default.

The V1 code travels alongside the image. An image alone shows what was drawn
but not why, so a critique working from the picture only can describe the
symptom and miss the line that caused it.

The schema block is duplicated from `codegen.py` rather than shared. The lab's
two prompts word it differently, so a single constant would mean rewriting one
of them — and prompt text is what the model reads, so it stays verbatim.
`validate_schema_blocks` guards the part that can be checked.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from . import codegen, config, dataset, executor, llm

# --- constants ---

# The schema exactly as the reflection prompt states it. Differs from
# `codegen.DATAFRAME_SCHEMA_BLOCK`; see the module docstring.
REFLECTION_SCHEMA_BLOCK = """\
- date   (datetime64 — already parsed; use df['date'].dt.year, etc.)
- time   (string, HH:MM — do NOT concatenate with date)
- cash_type (string: 'card' or 'cash')
- card   (string)
- price  (float)
- coffee_name (string)
- quarter (int, 1–4)
- month  (int, 1–12)
- year   (int)"""

REFLECTION_PROMPT = """\
You are a data visualization expert.
Your task: critique the attached chart and the original code against the given instruction,
then return improved matplotlib code.

Original code (for context):
{code_v1}

OUTPUT FORMAT (STRICT):
1) First line: a valid JSON object with ONLY the "feedback" field.
Example: {{"feedback": "The legend is unclear and the axis labels overlap."}}

2) After a newline, output ONLY the refined Python code wrapped in:
<execute_python>
...
</execute_python>

3) Import all necessary libraries in the code. Don't assume any imports from the original code.

HARD CONSTRAINTS:
- Do NOT include Markdown, backticks, or any extra prose outside the two parts above.
- Use pandas/matplotlib only (no seaborn).
- Assume df already exists; do not read from files.
- Save to '{out_path_v2}' with dpi={dpi}.
- Always call plt.close() at the end (no plt.show()).
- Include all necessary import statements.

IMPORTANT: The 'date' column is already a pandas datetime64 type.
- Do NOT concatenate 'date' with 'time' using string operations.
- To filter by year/quarter, use: df[df['year'] == 2024] or df['date'].dt.year == 2024
- The 'quarter' and 'year' columns already exist as integers; use them directly.

Schema (columns available in df):
{schema}

CRITICAL TYPE RULE: 'date' is already datetime64.
- NEVER do: df['date'] + ' ' + df['time']  ← this will crash
- ALWAYS filter by year/quarter using the integer columns: df[df['year'] == 2024]

Instruction:
{instruction}"""

# The response should open with the JSON object. When it does not, the lab
# falls back to the first brace pair anywhere in the body before giving up.
JSON_OBJECT_PATTERN = re.compile(r"\{.*?\}", re.DOTALL)

FEEDBACK_FIELD = "feedback"


# --- types ---


@dataclass(frozen=True)
class Reflection:
    """A critique and the revised code it came with.

    `parse_error` is set when the feedback could not be read as JSON. The lab
    stores the error text in the feedback field itself, which makes a parsing
    failure indistinguishable from a critique that happens to mention JSON.
    Keeping it separate means a caller can tell, and the raw response is kept
    either way so nothing is lost.
    """

    feedback: str
    code: str
    prompt: str
    raw_response: str
    request_summary: str
    parse_error: str | None = None

    @property
    def parsed_cleanly(self) -> bool:
        return self.parse_error is None


# --- helpers ---


def _feedback_from(response: str) -> tuple[str, str | None]:
    """Read the critique out of a response. Returns `(feedback, parse_error)`.

    Three attempts, matching the lab: the first line, then the first brace pair
    anywhere, then give up. Only the `feedback` field is read — the lab's
    fallback dict also carries a `refined_code` key, but nothing ever reads it;
    the code comes from the tags.
    """
    lines = response.strip().splitlines()
    first_line = lines[0].strip() if lines else ""

    try:
        return str(json.loads(first_line).get(FEEDBACK_FIELD, "")).strip(), None
    except (json.JSONDecodeError, AttributeError) as first_failure:
        first_error = str(first_failure)

    match = JSON_OBJECT_PATTERN.search(response)
    if match is None:
        return "", f"no JSON object in the response ({first_error})"

    try:
        return str(json.loads(match.group()).get(FEEDBACK_FIELD, "")).strip(), None
    except (json.JSONDecodeError, AttributeError) as second_failure:
        return "", f"found a JSON object but could not read it ({second_failure})"


# --- main export ---


def validate_schema_blocks() -> None:
    """Check that both prompts name every column the loader produces.

    Only the names. The rest of each line is guidance a person wrote after
    watching the model get it wrong — "do NOT concatenate with the date
    column", "already computed, use directly" — and no dtype dump produces
    that, so wording is left alone and only coverage is enforced.

    The two blocks are separate strings on purpose: prompt text is what the
    model reads, and the lab words the two differently. What must not happen is
    a column being added to the DataFrame and mentioned in only one of them.

    Raises:
        ValueError: a prompt does not mention some column.
    """
    blocks = {
        "generation": codegen.DATAFRAME_SCHEMA_BLOCK,
        "reflection": REFLECTION_SCHEMA_BLOCK,
    }
    for name, block in blocks.items():
        missing = [column for column in dataset.SCHEMA_COLUMNS if f"- {column}" not in block]
        if missing:
            raise ValueError(
                f"the {name} prompt never mentions {missing}; the model cannot use a column "
                f"it has not been told about."
            )


def build_reflection_prompt(instruction: str, code_v1: str, out_path_v2: str) -> str:
    """Render the step-3 prompt. Separated from the call so it can be inspected."""
    return REFLECTION_PROMPT.format(
        code_v1=code_v1,
        out_path_v2=out_path_v2,
        dpi=config.CHART_DPI,
        schema=REFLECTION_SCHEMA_BLOCK,
        instruction=instruction,
    )


def reflect_on_image_and_regenerate(
    chart_path: str | Path,
    instruction: str,
    model_name: str,
    out_path_v2: str,
    code_v1: str,
    log_request: bool = False,
) -> Reflection:
    """Critique the chart and return revised code. Mirrors the lab's function.

    Argument order follows the lab's. The return is a `Reflection` rather than a
    `(feedback, code)` tuple so that a parsing failure can be reported without
    disguising itself as a critique.

    Raises:
        MissingCodeBlockError: the response carried no `<execute_python>` block.
            The lab substitutes an empty string here, which turns a broken
            response into a V2 that silently never runs.
    """
    prompt = build_reflection_prompt(instruction, code_v1, out_path_v2)
    response, request_summary = llm.complete_with_image(
        model_name, prompt, chart_path, log_request=log_request
    )

    feedback, parse_error = _feedback_from(response)
    return Reflection(
        feedback=feedback,
        code=executor.extract_code(response),
        prompt=prompt,
        raw_response=response,
        request_summary=request_summary,
        parse_error=parse_error,
    )
