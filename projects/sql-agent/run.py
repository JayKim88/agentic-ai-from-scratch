"""Command line entry point.

    python run.py "Which color of product has the highest total sales?"
    python run.py "..." --condition text
    python run.py --index 1 --condition feedback-t0

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

from sql_agent import config, report
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


# --- main export ---


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.list:
        _list_questions()
        return 0

    question, expectation = _resolve_question(args)
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
