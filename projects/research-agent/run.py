"""CLI for the research agent.

Usage:
    python run.py "How do I build a new rocket company to compete with SpaceX?"
"""

import argparse
import logging
import sys

from research_agent import cache
from research_agent.config import CACHE_DIR, DEFAULT_MODEL
from research_agent.evals import EvalReport, evaluate
from research_agent.workflow import ResearchResult, run, save

LOG_FORMAT = "  %(levelname)s %(message)s"
CHECK_NAME_WIDTH = 16
CHECK_VALUE_WIDTH = 18


def _configure_logging(is_verbose: bool) -> None:
    # Tool calls are logged at INFO; without -v the run stays quiet apart from
    # the progress lines this module prints itself.
    level = logging.INFO if is_verbose else logging.WARNING
    logging.basicConfig(level=level, format=LOG_FORMAT)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def _print_progress(index: int, total: int, name: str) -> None:
    print(f"[{index}/{total}] {name} ...", flush=True)


def _print_summary(result: ResearchResult) -> None:
    trace = result.trace
    print()
    print(f"리포트    {result.report_path}")
    print(f"트레이스  {result.trace_path}")
    print()
    print(f"소요 시간  {trace.total_duration_seconds():.1f}s")
    print(f"도구 호출  {trace.total_tool_calls()}회")
    print(f"수집 소스  {result.source_count()}개")
    print(f"리포트     {len(result.report.split())} 단어")


def _print_evals(report: EvalReport) -> None:
    print()
    print(f"=== 평가  {report.passed_count}/{len(report.checks)} 통과 ===")
    for check in report.checks:
        mark = "PASS" if check.passed else "FAIL"
        name = check.name.ljust(CHECK_NAME_WIDTH)
        value = check.value.ljust(CHECK_VALUE_WIDTH)
        print(f"  [{mark}] {name} {value} {check.detail}".rstrip())


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the research agent on a topic.")
    parser.add_argument("topic", help="What to research.")
    parser.add_argument(
        "--model", default=DEFAULT_MODEL, help=f"aisuite model id (default: {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Log every tool call."
    )
    parser.add_argument(
        "--cache",
        action="store_true",
        help="Reuse tool results from a previous run of the same searches. "
        "Speeds up prompt tuning; do not use when the topic needs current data.",
    )
    parser.add_argument(
        "--no-eval", action="store_true", help="Skip the evaluation pass."
    )
    parser.add_argument(
        "--no-link-check",
        action="store_true",
        help="Skip fetching cited URLs during evaluation.",
    )
    args = parser.parse_args()

    _configure_logging(args.verbose)

    if args.cache:
        cache.enable(CACHE_DIR)

    print(f'주제: "{args.topic}"')
    print(f"모델: {args.model}")
    if args.cache:
        print("캐시: 사용 (도구 결과 재사용)")
    print()

    try:
        result = save(run(args.topic, model=args.model, on_progress=_print_progress))
    except RuntimeError as error:
        # Raised by require_openai_key() when credentials are missing.
        print(f"\n실행 실패: {error}", file=sys.stderr)
        return 1

    _print_summary(result)

    if args.no_eval:
        return 0

    report = evaluate(result, check_links=not args.no_link_check)
    _print_evals(report)
    return 0 if report.all_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
