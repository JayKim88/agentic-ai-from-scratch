"""Show each step's output, and keep a copy on disk.

The lab prints every intermediate artifact with `utils.print_html`: the sample
rows, the extracted code, the V1 chart, the critique, the revised code, the V2
chart. Its markdown says so plainly — *"you'll see both the reflection written
by the LLM and the new code it generated"*.

Dropping that as "notebook-only" would leave a workflow that emits two images
and nothing else, which is a poor way to study a pattern whose whole subject is
the critique in the middle. The HTML rendering goes; the showing stays, as
console output plus files under the run directory.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pandas as pd

# --- constants ---

RULE_WIDTH = 72
SAMPLE_ROWS = 5
CODE_PREVIEW_LINES = 40


# --- helpers ---


def _rule(title: str) -> str:
    return f"\n{title}\n{'─' * RULE_WIDTH}"


# --- main export ---


def heading(title: str) -> None:
    """Announce a step."""
    print(_rule(title))


def show_text(title: str, body: str, *, indent: str = "  ") -> None:
    """Print a block of prose — a critique, usually."""
    print(_rule(title))
    for line in textwrap.wrap(body.strip(), width=RULE_WIDTH - len(indent)) or [""]:
        print(f"{indent}{line}")


def show_code(title: str, code: str, *, limit: int = CODE_PREVIEW_LINES) -> None:
    """Print generated code, truncated so a long block stays readable."""
    print(_rule(title))
    lines = code.strip().splitlines()
    for line in lines[:limit]:
        print(f"  {line}")
    if len(lines) > limit:
        print(f"  … {len(lines) - limit} more lines")


def show_artifact(title: str, path: str | Path) -> None:
    """Point at a file the step produced, with its size as proof it exists."""
    target = Path(path)
    size = f"{target.stat().st_size:,} bytes" if target.exists() else "MISSING"
    print(_rule(title))
    print(f"  {target}  ({size})")


def show_dataframe_sample(df: pd.DataFrame, rows: int = SAMPLE_ROWS) -> None:
    """Show a few rows, as the lab's workflow does before anything else."""
    print(_rule(f"Dataset — {len(df):,} rows, {len(df.columns)} columns"))
    with pd.option_context("display.width", 200, "display.max_columns", None):
        for line in df.sample(n=rows).to_string(index=False).splitlines():
            print(f"  {line}")


def save_artifacts(directory: str | Path, **artifacts: str) -> dict[str, Path]:
    """Write each named artifact to `directory`, returning where each went.

    Suffixes come from the name: anything ending in `_code` is Python, the rest
    is text. Keeps the run inspectable after the console has scrolled away.
    """
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)

    written = {}
    for name, content in artifacts.items():
        suffix = ".py" if name.endswith("_code") else ".txt"
        path = target / f"{name}{suffix}"
        path.write_text(content, encoding="utf-8")
        written[name] = path

    return written
