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


def _chart_path(basename: str, version: str) -> Path:
    return config.CHARTS_DIR / f"{basename}_{version}.png"


def _run_code(code: str, df: pd.DataFrame, chart_path: Path, workdir: Path, version: str):
    """Execute generated code, or raise with what went wrong."""
    result = executor.execute_code(code, df, chart_path, workdir)
    if not result.succeeded:
        raise ChartExecutionError(f"{version} did not produce a chart. {result.failure_summary()}")
    return result


# --- main export ---


def generate_and_execute_v1(
    df: pd.DataFrame,
    instruction: str,
    basename: str,
    generation_model: str,
    run_trace: trace.RunTrace,
    verbose: bool = False,
) -> tuple[str, Path]:
    """Lab steps 1 and 2. Returns `(code_v1, chart_v1)`."""
    chart_path = _chart_path(basename, VERSION_ONE)

    report.heading("Step 1 — generating chart code (V1)")
    with run_trace.timed("generate_v1", model=generation_model) as step:
        response = codegen.generate_chart_code(instruction, generation_model, str(chart_path))
        code = executor.extract_code(response)
        step.detail["code_lines"] = len(code.splitlines())

    if verbose:
        report.show_code("Extracted code (V1)", code)

    report.heading("Step 2 — executing chart code (V1)")
    with run_trace.timed("execute_v1") as step:
        _run_code(code, df, chart_path,
                  config.CHARTS_DIR / f"{basename}_{VERSION_ONE}_work", VERSION_ONE)
        step.artifact = str(chart_path)
    report.show_artifact("Generated chart (V1)", chart_path)

    return code, chart_path


def reflect_and_execute_v2(
    df: pd.DataFrame,
    instruction: str,
    basename: str,
    code_v1: str,
    chart_v1: Path,
    reflection_model: str,
    run_trace: trace.RunTrace,
    verbose: bool = False,
) -> tuple[reflect.Reflection, Path]:
    """Lab steps 3 and 4. Returns `(reflection, chart_v2)`."""
    chart_path = _chart_path(basename, VERSION_TWO)

    report.heading("Step 3 — critiquing V1 and revising the code")
    with run_trace.timed("reflect", model=reflection_model) as step:
        reflection = reflect.reflect_on_image_and_regenerate(
            chart_path=chart_v1,
            instruction=instruction,
            model_name=reflection_model,
            out_path_v2=str(chart_path),
            code_v1=code_v1,
            log_request=verbose,
        )
        step.detail.update(
            parsed_cleanly=reflection.parsed_cleanly, parse_error=reflection.parse_error
        )

    report.show_text("Reflection feedback on V1", reflection.feedback or "(empty)")
    if reflection.parse_error:
        print(f"  ⚠ feedback could not be parsed — {reflection.parse_error}")
    if verbose:
        report.show_code("Revised code (V2)", reflection.code)

    report.heading("Step 4 — executing revised chart code (V2)")
    with run_trace.timed("execute_v2") as step:
        _run_code(reflection.code, df, chart_path,
                  config.CHARTS_DIR / f"{basename}_{VERSION_TWO}_work", VERSION_TWO)
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
    report.show_dataframe_sample(df)

    run_trace = trace.RunTrace(
        instruction=user_instructions,
        generation_model=generation_model,
        reflection_model=reflection_model,
        dataset_path=str(source),
    )

    code_v1, chart_v1 = generate_and_execute_v1(
        df, user_instructions, image_basename, generation_model, run_trace, verbose
    )
    reflection, chart_v2 = reflect_and_execute_v2(
        df, user_instructions, image_basename, code_v1, chart_v1,
        reflection_model, run_trace, verbose
    )

    written = report.save_artifacts(
        config.CHARTS_DIR / f"{image_basename}_artifacts",
        v1_code=code_v1,
        v2_code=reflection.code,
        feedback=reflection.feedback,
        reflection_raw=reflection.raw_response,
    )
    trace_path = run_trace.save(config.TRACES_DIR)

    report.heading("Artifacts")
    for name, path in {**written, "trace": trace_path}.items():
        print(f"  {name:16} {path}")

    return {
        "code_v1": code_v1,
        "chart_v1": str(chart_v1),
        "feedback": reflection.feedback,
        "code_v2": reflection.code,
        "chart_v2": str(chart_v2),
    }
