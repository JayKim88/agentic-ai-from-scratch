"""The lab's four steps, end to end.

    1. generate V1 code      2. run it
    3. critique the image    4. run the revised code

Execution is hard-wired to follow each generation, which the lab states as a
deliberate choice rather than a shortcut — *"intentionally hard-coded … ensures
you see each draft's output before moving on"*. The model decides what the code
says, never when it runs.

A failed execution stops the run. With no chart there is nothing to critique,
so continuing would mean inventing a step the lab does not have. Retrying on
the error is B1's job, deliberately kept out of the reproduction.

The two halves are separate functions so they can be driven one at a time, the
way the lab's sections 3.1 to 3.4 do before section 4 joins them up.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd

from . import codegen, config, dataset, executor, reflect, report, trace

# --- constants ---

VERSION_ONE = "v1"
VERSION_TWO = "v2"


# --- types ---


class ChartExecutionError(RuntimeError):
    """Generated code did not produce the chart it was told to."""


# --- helpers ---


def new_run_directory(basename: str) -> Path:
    """A fresh directory for this run, named for when it started.

    The lab tells the reader to change `image_basename` between runs so results
    are not overwritten. Leaving that to the person means one forgotten flag
    destroys the run they wanted to compare against, so the timestamp does it
    instead — the basename stays a label rather than a safety measure.
    """
    stamp = datetime.now().strftime(config.RUN_DIRECTORY_FORMAT)
    directory = config.RUNS_DIR / f"{stamp}_{basename}"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _chart_path(run_dir: Path, basename: str, version: str) -> Path:
    # Filenames keep the lab's `{base}_v1.png` shape; the run directory is what
    # separates one invocation from the next.
    return run_dir / f"{basename}_{version}.png"


def _run_code(code: str, df: pd.DataFrame, chart_path: Path, workdir: Path, version: str):
    """Execute generated code, or raise with what went wrong.

    The working directory holds what the subprocess needed — the snippet and a
    pickled copy of the frame, most of it a duplicate of `artifacts/` and of the
    dataset. On success it is scaffolding and gets removed; on failure it is
    left in place, because that is the run someone will want to poke at.
    """
    result = executor.execute_code(code, df, chart_path, workdir)
    if not result.succeeded:
        raise ChartExecutionError(
            f"{version} did not produce a chart. {result.failure_summary()}\n"
            f"What it ran is in {workdir}."
        )

    shutil.rmtree(workdir, ignore_errors=True)
    return result


# --- main export ---


def generate_and_execute_v1(
    df: pd.DataFrame,
    instruction: str,
    run_dir: Path,
    basename: str,
    generation_model: str,
    run_trace: trace.RunTrace,
    verbose: bool = False,
) -> tuple[str, Path]:
    """Lab steps 1 and 2. Returns `(code_v1, chart_v1)`, saving both plus the prompt."""
    chart_path = _chart_path(run_dir, basename, VERSION_ONE)

    artifacts = run_dir / config.ARTIFACTS_SUBDIRECTORY

    report.heading("Step 1 — generating chart code (V1)")
    with run_trace.timed("generate_v1", model=generation_model) as step:
        prompt = codegen.build_generation_prompt(instruction, str(chart_path))
        response = codegen.generate_chart_code(instruction, generation_model, str(chart_path))

        # Saved before parsing, and parsing before executing. Whatever fails,
        # what went in and what came back is already on disk — those are what a
        # failed run gets investigated with.
        report.save_artifacts(artifacts, v1_prompt=prompt, v1_raw=response)
        code = executor.extract_code(response)
        report.save_artifacts(artifacts, v1_code=code)
        step.detail["code_lines"] = len(code.splitlines())

    if verbose:
        report.show_code("Extracted code (V1)", code)

    report.heading("Step 2 — executing chart code (V1)")
    with run_trace.timed("execute_v1") as step:
        _run_code(code, df, chart_path, run_dir / f"{VERSION_ONE}_work", VERSION_ONE)
        step.artifact = str(chart_path)
    report.show_artifact("Generated chart (V1)", chart_path)

    return code, chart_path


def reflect_and_execute_v2(
    df: pd.DataFrame,
    instruction: str,
    run_dir: Path,
    basename: str,
    code_v1: str,
    chart_v1: Path,
    reflection_model: str,
    run_trace: trace.RunTrace,
    verbose: bool = False,
) -> tuple[reflect.Reflection, Path]:
    """Lab steps 3 and 4. Returns `(reflection, chart_v2)`, saving the critique too."""
    chart_path = _chart_path(run_dir, basename, VERSION_TWO)

    artifacts = run_dir / config.ARTIFACTS_SUBDIRECTORY
    prompt = reflect.build_reflection_prompt(instruction, code_v1, str(chart_path))
    report.save_artifacts(artifacts, v2_prompt=prompt)

    report.heading("Step 3 — critiquing V1 and revising the code")
    with run_trace.timed("reflect", model=reflection_model) as step:
        try:
            reflection = reflect.reflect_on_image_and_regenerate(
                chart_path=chart_v1,
                instruction=instruction,
                model_name=reflection_model,
                out_path_v2=str(chart_path),
                code_v1=code_v1,
                log_request=verbose,
            )
        except executor.MissingCodeBlockError as error:
            # The reply is the only record of why parsing failed; keep it before
            # the error leaves this frame.
            report.save_artifacts(artifacts, reflection_raw=error.response)
            raise
        step.detail.update(
            parsed_cleanly=reflection.parsed_cleanly,
            parse_error=reflection.parse_error,
            request=reflection.request_summary,
        )

    report.show_text("Reflection feedback on V1", reflection.feedback or "(empty)")
    if reflection.parse_error:
        print(f"  ⚠ feedback could not be parsed — {reflection.parse_error}")
    if verbose:
        report.show_code("Revised code (V2)", reflection.code)

    report.save_artifacts(
        artifacts,
        feedback=reflection.feedback,
        v2_code=reflection.code,
        reflection_raw=reflection.raw_response,
    )

    report.heading("Step 4 — executing revised chart code (V2)")
    with run_trace.timed("execute_v2") as step:
        _run_code(reflection.code, df, chart_path, run_dir / f"{VERSION_TWO}_work", VERSION_TWO)
        step.artifact = str(chart_path)
    report.show_artifact("Regenerated chart (V2)", chart_path)

    return reflection, chart_path


def run_workflow(
    dataset_path: str | Path | None = None,
    user_instructions: str = "",
    generation_model: str = config.DEFAULT_GENERATION_MODEL,
    reflection_model: str = config.DEFAULT_REFLECTION_MODEL,
    image_basename: str = config.DEFAULT_IMAGE_BASENAME,
    verbose: bool = False,
) -> dict:
    """Run all four steps. Returns the lab's five artifacts.

    `image_basename` decides the filenames, and the lab is emphatic about
    changing it between runs — *"so each run saves its results under a new
    filename"*. Without that, a comparison overwrites the thing being compared.

    Raises:
        ChartExecutionError: either version failed to draw its chart.
    """
    reflect.validate_schema_blocks()

    source = Path(dataset_path) if dataset_path else dataset.resolve_dataset_path()
    df = dataset.load_and_prepare_data(source)
    run_dir = new_run_directory(image_basename)
    report.show_dataframe_sample(df)

    run_trace = trace.RunTrace(
        instruction=user_instructions,
        generation_model=generation_model,
        reflection_model=reflection_model,
        dataset_path=str(source),
    )

    code_v1, chart_v1 = generate_and_execute_v1(
        df, user_instructions, run_dir, image_basename, generation_model, run_trace, verbose
    )
    reflection, chart_v2 = reflect_and_execute_v2(
        df, user_instructions, run_dir, image_basename, code_v1, chart_v1,
        reflection_model, run_trace, verbose
    )

    run_trace.save(run_dir / config.TRACE_FILENAME)
    report.show_artifact("Run directory", run_dir)

    return {
        "code_v1": code_v1,
        "chart_v1": str(chart_v1),
        "feedback": reflection.feedback,
        "code_v2": reflection.code,
        "chart_v2": str(chart_v2),
    }
