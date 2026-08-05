#!/usr/bin/env python
"""Command line entry point for the chart agent.

Runs all four steps by default. `--only v1` and `--from-chart` split them, which
is how the lab works through sections 3.1 to 3.4 before joining them in section
4 — reading the critique on its own is easier than reading it inside a full run.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from chart_agent import config, dataset, report, trace, workflow

# --- constants ---

LECTURE_INSTRUCTION = (
    "Create a plot comparing Q1 coffee sales in 2024 and 2025 using the data in coffee_sales.csv."
)

STAGE_V1_ONLY = "v1"

# What `generate_and_execute_v1` saves; `--from-chart` reads it back.
V1_CODE_FILENAME = "v1_code.py"

# Recorded in the trace when a partial run never reaches that model.
SKIPPED = "(skipped)"


# --- helpers ---


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a chart, critique it, and redraw it.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Default instruction:\n  {LECTURE_INSTRUCTION}",
    )
    parser.add_argument("instruction", nargs="?", default=LECTURE_INSTRUCTION)
    parser.add_argument("--dataset", help="CSV to plot (defaults to the lab's, then the generated one)")
    parser.add_argument("--gen-model", default=config.DEFAULT_GENERATION_MODEL)
    parser.add_argument("--reflect-model", default=config.DEFAULT_REFLECTION_MODEL)
    parser.add_argument(
        "--basename",
        default=config.DEFAULT_IMAGE_BASENAME,
        help="label for this run; appears in the run directory and chart filenames",
    )
    parser.add_argument("--only", choices=[STAGE_V1_ONLY], help="stop after generating and running V1")
    parser.add_argument(
        "--from-chart",
        help="skip V1 and critique this chart from an earlier run (its code is read alongside)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="show generated code and requests")
    return parser.parse_args(argv)


def _dataset_path(args: argparse.Namespace) -> Path:
    return Path(args.dataset) if args.dataset else dataset.resolve_dataset_path()


def _new_trace(args: argparse.Namespace, source: Path, *, generation: str, reflection: str):
    return trace.RunTrace(
        instruction=args.instruction,
        generation_model=generation,
        reflection_model=reflection,
        dataset_path=str(source),
    )


def _code_beside(chart: Path) -> Path:
    """Where a run keeps the code that drew `chart`."""
    return chart.parent / config.ARTIFACTS_SUBDIRECTORY / V1_CODE_FILENAME


def _run_from_existing_chart(args: argparse.Namespace) -> int:
    """Critique a chart from an earlier run, then run the revision.

    Both the image and the code go in, as the lab's function requires. The
    lab's own section-by-section flow has the code too — a notebook keeps
    `code_v1` in a variable between cells — so passing the image alone would
    reproduce the shape of that flow without its substance.

    It also produces worse output. The step returns *revised* code, and a model
    given no code to revise writes one from scratch, which collides with the
    prompt's "assume df already exists". Claude did exactly that twice, ending
    up with `df = None`; with the code alongside, the same model and prompt
    succeeded.
    """
    chart = Path(args.from_chart)
    if not chart.exists():
        print(f"error: {chart} does not exist", file=sys.stderr)
        return 1

    code_file = _code_beside(chart)
    if not code_file.exists():
        print(
            f"error: no {V1_CODE_FILENAME} beside {chart}.\n"
            f"       Looked in {code_file.parent}. Point at a chart from a run directory —\n"
            f"       the reflection step revises code, so it needs the code that drew the chart.",
            file=sys.stderr,
        )
        return 1

    source = _dataset_path(args)
    df = dataset.load_and_prepare_data(source)
    run_dir = workflow.new_run_directory(args.basename)
    run_trace = _new_trace(args, source, generation=SKIPPED, reflection=args.reflect_model)

    workflow.reflect_and_execute_v2(
        df=df,
        instruction=args.instruction,
        run_dir=run_dir,
        basename=args.basename,
        code_v1=code_file.read_text(encoding="utf-8"),
        chart_v1=chart,
        reflection_model=args.reflect_model,
        run_trace=run_trace,
        verbose=args.verbose,
    )
    run_trace.save(run_dir / config.TRACE_FILENAME)
    report.show_artifact("Run directory", run_dir)
    return 0


def _run_v1_only(args: argparse.Namespace) -> int:
    source = _dataset_path(args)
    df = dataset.load_and_prepare_data(source)
    run_dir = workflow.new_run_directory(args.basename)
    report.show_dataframe_sample(df)

    run_trace = _new_trace(args, source, generation=args.gen_model, reflection=SKIPPED)
    workflow.generate_and_execute_v1(
        df, args.instruction, run_dir, args.basename, args.gen_model, run_trace, args.verbose
    )
    run_trace.save(run_dir / config.TRACE_FILENAME)
    report.show_artifact("Run directory", run_dir)
    return 0


# --- main export ---


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    try:
        if args.from_chart:
            return _run_from_existing_chart(args)
        if args.only == STAGE_V1_ONLY:
            return _run_v1_only(args)

        workflow.run_workflow(
            dataset_path=args.dataset,
            user_instructions=args.instruction,
            generation_model=args.gen_model,
            reflection_model=args.reflect_model,
            image_basename=args.basename,
            verbose=args.verbose,
        )
    except (workflow.ChartExecutionError, RuntimeError, ValueError, FileNotFoundError) as error:
        print(f"\nerror: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
