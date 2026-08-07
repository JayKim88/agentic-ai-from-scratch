"""Command line entry point.

    python run.py "Which color of product has the highest total sales?"
    python run.py "..." --condition text
    python run.py --index 1 --condition feedback-t0
    python run.py --index 0 --all-conditions      # repeat each condition, count passes
    python run.py --index 0 --compare-models      # same query, four reviewers

A question can be typed out or picked from the evaluation set by index. Picking
one is what makes scoring possible: a typed question has no known answer, so
the run is shown but not graded.

Exits 1 when a scored run got the wrong answer — the same convention a test
runner uses. A wrong answer is an outcome worth measuring, not a crash, so
nothing else about the run changes.
"""

from __future__ import annotations

import argparse
import sys

from sql_agent import batch, config, report
from sql_agent.invariants import EXPECTATIONS
from sql_agent.trace import RunTrace
from sql_agent.workflow import CONDITIONS, DEFAULT_CONDITION, run_sql_workflow

# --- constants ---

FIRST_ITERATION = 1


# --- helpers ---


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the SQL reflection workflow.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="conditions:\n" + "\n".join(
            f"  {name:<12} {c.description}" for name, c in CONDITIONS.items()
        ),
    )
    parser.add_argument("question", nargs="?", help="question to ask, in plain English")
    parser.add_argument(
        "--index", type=int, metavar="N",
        help="use evaluation question N instead, so the run can be scored (--list to see them)",
    )
    parser.add_argument("--list", action="store_true", help="show the evaluation questions and exit")
    parser.add_argument(
        "--condition", default=DEFAULT_CONDITION, choices=list(CONDITIONS),
        help=f"how to review the first query (default: {DEFAULT_CONDITION})",
    )
    parser.add_argument(
        "--all-conditions", action="store_true",
        help="repeat every condition and report pass rates (needs --index)",
    )
    parser.add_argument(
        "--compare-models", action="store_true",
        help="hand one fixed query to each model to review (needs --index)",
    )
    parser.add_argument("--gen-model", default=config.DEFAULT_GENERATION_MODEL)
    parser.add_argument("--eval-model", default=config.DEFAULT_EVALUATION_MODEL)
    parser.add_argument("--label", default=config.DEFAULT_RUN_LABEL, help="names the run directory")
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="also print the schema the model was given",
    )
    return parser


def _list_questions() -> None:
    print("Evaluation questions — these have known answers, so runs on them are scored.\n")
    for index, expectation in enumerate(EXPECTATIONS):
        answer = f"{expectation.key} / " if expectation.key else ""
        print(f"  {index}  {expectation.question}")
        print(f"     → {answer}{expectation.value:,}")


def _resolve_question(args) -> tuple[str, object | None]:
    """The question to ask and its known answer, if it has one.

    Raises:
        SystemExit: neither a question nor an index was given, or the index is
            out of range.
    """
    if args.index is not None:
        if not 0 <= args.index < len(EXPECTATIONS):
            raise SystemExit(
                f"--index must be 0..{len(EXPECTATIONS) - 1}; use --list to see them."
            )
        expectation = EXPECTATIONS[args.index]
        return expectation.question, expectation

    if args.question:
        return args.question, None

    raise SystemExit("give a question, or --index N to pick one that can be scored.")


def _show_progress(label: str, iteration: int, outcome) -> None:
    mark = "pass" if outcome.is_correct else "FAIL"
    print(f"  {label:<22} {iteration:>2}  {mark}")


def _run_batch(args, expectation) -> int:
    """Repeat runs and print the counts. Returns the process exit code."""
    if expectation is None:
        raise SystemExit("--all-conditions and --compare-models need --index N to score against.")

    directory = report.new_run_directory(args.label)
    print(f"{expectation.question}\nSaving to {directory.relative_to(config.PROJECT_ROOT)}\n")

    if args.all_conditions:
        tallies = batch.run_conditions(
            expectation, directory,
            generation_model=args.gen_model, evaluation_model=args.eval_model,
            on_progress=_show_progress,
        )
        note = ("repeats differ by condition: the temperature-0 ones are close to "
                "deterministic, so the calls go to the one that varies")
        print("\n" + batch.format_table(tallies, "Pass rate by condition"))
        print(f"\n  {note}")
        batch.save_summary(expectation.question, tallies, directory, note)

    if args.compare_models:
        fixed_sql, tallies, baseline = batch.run_model_comparison(
            expectation, directory,
            generation_model=args.gen_model, on_progress=_show_progress,
        )
        note = "every model reviewed the same V1 and the same execution output"
        print("\n" + batch.format_table(tallies, "Pass rate by reviewing model"))
        print(f"\n  {note}\n")
        print("  V1 every reviewer saw:")
        print("\n".join(f"    {line}" for line in fixed_sql.splitlines()))
        print("\n  and its output:")
        print("\n".join(f"    {line}" for line in baseline.to_markdown().splitlines()))
        batch.save_summary(
            expectation.question, tallies, directory, note, name="summary_models.json"
        )

        rescored = batch.rescore_without_fences(directory, expectation)
        if any(before != after for before, after in rescored.values()):
            print("\n  Scored again with the markdown fence removed — no model was called.")
            print("  The lab strips a fence off generated SQL but not off a review, so a")
            print("  correct answer that arrived fenced counts as a failure above.\n")
            for label, (before, after) in rescored.items():
                mark = "   <- fence, not reasoning" if before != after else ""
                print(f"    {label.removeprefix('model_'):<16} {before} -> {after}{mark}")

    return 0


# --- main export ---


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.list:
        _list_questions()
        return 0

    question, expectation = _resolve_question(args)

    if args.all_conditions or args.compare_models:
        return _run_batch(args, expectation)

    trace = RunTrace(question, args.condition, args.gen_model, args.eval_model)

    result = run_sql_workflow(
        question,
        condition=args.condition,
        generation_model=args.gen_model,
        evaluation_model=args.eval_model,
        expectation=expectation,
        trace=trace,
    )

    report.show(result, show_schema=args.verbose)

    directory = report.iteration_directory(
        report.new_run_directory(args.label), args.condition, FIRST_ITERATION
    )
    report.save(result, trace, directory)
    print(f"\nSaved to {directory.relative_to(config.PROJECT_ROOT)}  ({trace.total_seconds}s)")

    if expectation is None:
        return 0
    return 0 if result.is_correct else 1


if __name__ == "__main__":
    sys.exit(main())
