"""Ask a model for the first draft of the plotting code (lab step 1).

The prompt's centre of gravity is the schema block. The model never sees the
CSV, so without a column listing it invents names or tries to parse dates by
hand — the lab's own prompt spends more space on the schema than on the task.
That block is a module constant here because the lab pastes it into both its
prompts, and a schema that drifts between the two is a bug waiting to happen.
"""

from __future__ import annotations

from . import config, llm

# --- constants ---

# The nine columns exactly as the lab words them, en dashes and all.
#
# Half of each line is not a type but an instruction — "do NOT concatenate with
# the date column", "already computed, use directly" — written by someone who
# watched the model get it wrong. df.dtypes cannot produce that, which is why
# this is a hand-written string and only the column names are machine-checked.
# `reflect.py` carries its own wording; see `validate_schema_blocks`.
DATAFRAME_SCHEMA_BLOCK = """\
- date   (datetime64 — already parsed; use df['date'].dt.year, df['date'].dt.month, etc.)
- time   (string, HH:MM — do NOT concatenate or combine with the date column)
- cash_type (string: 'card' or 'cash')
- card (string)
- price (number)
- coffee_name (string)
- quarter (int, 1–4 — already computed, use directly)
- month  (int, 1–12 — already computed, use directly)
- year   (int, e.g. 2024 — already computed, use directly)"""

# Verbatim from the lab, down to the missing full stop on item 7 and the
# shouted CRITICAL on item 8.
#
# Leaving the emphasis in place is deliberate. B1 asks whether an execution
# feedback loop makes those warnings unnecessary — the lab repeats the same
# `date` caution three times across its two prompts, which is what prompting
# under no feedback looks like. Softening the wording now would erase the
# baseline that experiment needs.
CODE_REQUIREMENTS = """\
1. Assume the DataFrame is already loaded as 'df'.
2. Use matplotlib for plotting.
3. Add clear title, axis labels, and legend if needed.
4. Save the figure as '{out_path}' with dpi={dpi}.
5. Do not call plt.show().
6. Close all plots with plt.close().
7. Add all necessary import python statements
8. CRITICAL: 'date' is datetime64 — never use string concatenation on it.
   Filter by year/quarter using the 'year' and 'quarter' integer columns."""

GENERATION_PROMPT = """\
You are a data visualization expert.

Return your answer *strictly* in this format:

<execute_python>
# valid python code here
</execute_python>

Do not add explanations, only the tags and the code.

The code should create a visualization from a DataFrame 'df' with these columns:
{schema}

User instruction: {instruction}

Requirements for the code:
{requirements}

Return ONLY the code wrapped in <execute_python> tags."""


# --- main export ---


def build_generation_prompt(instruction: str, out_path: str) -> str:
    """Render the step-1 prompt. Separated from the call so it can be inspected."""
    return GENERATION_PROMPT.format(
        schema=DATAFRAME_SCHEMA_BLOCK,
        instruction=instruction,
        requirements=CODE_REQUIREMENTS.format(out_path=out_path, dpi=config.CHART_DPI),
    )


def generate_chart_code(instruction: str, model: str, out_path_v1: str) -> str:
    """Return the model's raw reply, tags and all.

    Argument order and names follow the lab's. An earlier version put `model`
    last so it could carry a default; the default now lives in `workflow.py`,
    where the caller is, rather than bending the signature to hold it.

    Extraction stays in `executor.extract_code` so a malformed reply can be
    logged whole — the lab drops it silently.
    """
    return llm.complete(model, build_generation_prompt(instruction, out_path_v1))
