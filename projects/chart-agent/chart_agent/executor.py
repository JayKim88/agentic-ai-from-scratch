"""Extract `<execute_python>` blocks and run them in an isolated subprocess.

The lab runs generated code inline:

    match = re.search(r"<execute_python>([\\s\\S]*?)</execute_python>", code_v1)
    if match:
        exec(match.group(1).strip(), {"df": df})

Two things change here and neither alters what the code can do.

First, a missing tag is an error rather than a silent skip — the lab's `if
match:` has no `else`, so a malformed response quietly produces no chart and
the workflow carries on as if it had.

Second, execution moves to a subprocess. Inline `exec` lets one bad line kill
the whole run and gives no way to read what went wrong; a child process
survives its own failure and hands back stderr, which is the raw material for
the execution-feedback loop the lecture calls for and the lab omits.

The caller's DataFrame travels to the child through a pickle file, because
processes share no memory. Pickle rather than CSV so that dtypes survive: a CSV
round trip would turn `date` back into text and force the child to re-derive
`quarter`/`month`/`year`, which would put the nine-column contract in two
places. Passing the object also means the child receives *the caller's* frame —
a filtered or reshaped one works exactly as well as the full table.

That hand-off keeps the child free of project imports. It needs pandas and
nothing else, so there is no `sys.path` surgery and no path arithmetic that
breaks when the package moves.

The execution context still holds nothing but `df`, so generated code must
import everything it uses — exactly the constraint the lab's prompt states.

⚠ A subprocess is isolation, not a sandbox. There is no syscall filtering
here; this runs LLM-authored code on the local machine and is meant for
learning, not for untrusted input. (Unpickling can execute code too, but the
file is one we just wrote, and the child is already running arbitrary
model-authored code — it adds no new exposure.)
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

# --- constants ---

CODE_BLOCK_PATTERN = re.compile(r"<execute_python>([\s\S]*?)</execute_python>")

EXECUTION_TIMEOUT_SECONDS = 30
SUCCESS_RETURN_CODE = 0
TIMEOUT_RETURN_CODE = -1

# Generated code never sets a backend and the lab prompt never asks for one, so
# matplotlib would pick the platform default (macosx here). Forcing a headless
# backend through the environment keeps the generated code untouched.
HEADLESS_MATPLOTLIB_BACKEND = "Agg"

# `-I` drops the working directory from the module search path. Without it a
# file the run happens to leave in the workdir — `json.py`, say — would shadow
# the standard library for the generated code.
ISOLATED_INTERPRETER_FLAG = "-I"

GENERATED_CODE_FILENAME = "generated.py"
DATAFRAME_FILENAME = "df.pkl"

_RUNNER_TEMPLATE = """\
import pandas as pd

df = pd.read_pickle({dataframe_path!r})
source = open({code_path!r}, encoding="utf-8").read()
exec(compile(source, "<generated>", "exec"), {{"df": df}})
"""


# --- types ---


@dataclass(frozen=True)
class ExecutionResult:
    """What running one generated snippet produced."""

    code: str
    returncode: int
    stdout: str
    stderr: str
    chart_path: Path
    timed_out: bool
    timeout_seconds: int

    @property
    def succeeded(self) -> bool:
        """True only when the process exited cleanly *and* left a chart behind.

        Exit code alone is not enough: code that forgets `savefig`, or writes to
        a different path than it was told to, still exits zero.
        """
        return self.returncode == SUCCESS_RETURN_CODE and self.chart_path.exists()

    def failure_summary(self) -> str:
        """A short description of what went wrong, for feeding back to a model."""
        if self.succeeded:
            return ""
        if self.timed_out:
            return f"Execution exceeded {self.timeout_seconds}s and was terminated."
        if self.returncode != SUCCESS_RETURN_CODE:
            return self.stderr.strip() or f"Process exited with code {self.returncode}."
        return f"Process exited cleanly but wrote no file at {self.chart_path}."


class MissingCodeBlockError(ValueError):
    """The model's response carried no `<execute_python>` block.

    Carries the response so a caller can save it before re-raising. A reply that
    could not be parsed is the one most worth reading afterwards.
    """

    def __init__(self, message: str, response: str = "") -> None:
        super().__init__(message)
        self.response = response


# --- helpers ---


def _child_environment() -> dict[str, str]:
    return {**os.environ, "MPLBACKEND": HEADLESS_MATPLOTLIB_BACKEND}


def _decode(stream: str | bytes | None) -> str:
    """TimeoutExpired hands back bytes or None depending on how it was raised."""
    if stream is None:
        return ""
    if isinstance(stream, bytes):
        return stream.decode("utf-8", errors="replace")
    return stream


# --- main export ---


def extract_code(response: str) -> str:
    """Pull the Python source out of a model response.

    Raises:
        MissingCodeBlockError: no `<execute_python>` block was found. The lab
            skips silently here, which turns a malformed response into a
            missing chart with no explanation.
    """
    match = CODE_BLOCK_PATTERN.search(response)
    if match is None:
        preview = response.strip()[:200] or "(empty response)"
        raise MissingCodeBlockError(
            f"no <execute_python> block in the response. Response began: {preview!r}",
            response=response,
        )

    return match.group(1).strip()


def execute_code(
    code: str,
    df: pd.DataFrame,
    chart_path: str | Path,
    workdir: str | Path,
    timeout: int = EXECUTION_TIMEOUT_SECONDS,
) -> ExecutionResult:
    """Run `code` in a child process with `df` in scope, and report what happened.

    `chart_path` is resolved to absolute form before being handed over, because
    the child runs in `workdir` rather than in the project — a relative
    `chart_v1.png` would land somewhere nobody looks for it afterwards.

    Failures are returned, not raised: a crashed snippet is the input to the
    next reflection step, not an error for the caller to handle.
    """
    work_dir = Path(workdir)
    work_dir.mkdir(parents=True, exist_ok=True)

    chart_target = Path(chart_path).resolve()
    chart_target.parent.mkdir(parents=True, exist_ok=True)

    code_file = work_dir / GENERATED_CODE_FILENAME
    code_file.write_text(code, encoding="utf-8")

    dataframe_file = work_dir / DATAFRAME_FILENAME
    df.to_pickle(dataframe_file)

    runner = _RUNNER_TEMPLATE.format(
        dataframe_path=str(dataframe_file),
        code_path=str(code_file),
    )
    command = [sys.executable, ISOLATED_INTERPRETER_FLAG, "-c", runner]

    try:
        completed = subprocess.run(
            command,
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_child_environment(),
        )
    except subprocess.TimeoutExpired as expired:
        return ExecutionResult(
            code=code,
            returncode=TIMEOUT_RETURN_CODE,
            stdout=_decode(expired.stdout),
            stderr=_decode(expired.stderr),
            chart_path=chart_target,
            timed_out=True,
            timeout_seconds=timeout,
        )

    return ExecutionResult(
        code=code,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        chart_path=chart_target,
        timed_out=False,
        timeout_seconds=timeout,
    )
