"""The seven-step pipeline.

Step order is hard-coded here — the programmer decides the sequence, the model
only decides which tools to reach for inside step 2. That makes this workflow
semi-autonomous in the terms module 1 used. Letting a planner choose the steps
is module 5 territory and deliberately out of scope.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import agents
from .config import DEFAULT_MODEL, REPORTS_DIR, TRACES_DIR
from .llm import timed_call
from .trace import RunTrace, StepTrace

SLUG_MAX_LENGTH = 40
SLUG_FALLBACK = "report"

ProgressCallback = Callable[[int, int, str], None]

STEP_NAMES = [
    "리서치 계획 수립",
    "자료 수집",
    "종합·순위화",
    "아웃라인 작성",
    "초안 작성",
    "비평 (반성)",
    "수정 → 최종 리포트",
]
TOTAL_STEPS = len(STEP_NAMES)


@dataclass
class ResearchResult:
    """Everything one run produced, including the intermediates worth comparing."""

    topic: str
    report: str
    draft: str
    critique: str
    trace: RunTrace
    report_path: Path | None = None
    trace_path: Path | None = None
    sources: str = ""

    def source_count(self) -> int:
        return len(self.trace.collected_urls())


def slugify(topic: str) -> str:
    """Turn a topic into a filename-safe slug, keeping non-ASCII words intact."""
    cleaned = re.sub(r"[^\w\s-]", "", topic, flags=re.UNICODE).strip().lower()
    slug = re.sub(r"[\s_]+", "-", cleaned)[:SLUG_MAX_LENGTH].strip("-")
    return slug or SLUG_FALLBACK


def _noop_progress(index: int, total: int, name: str) -> None:
    """Default callback so the workflow never has to check for None."""


def run(
    topic: str,
    model: str = DEFAULT_MODEL,
    on_progress: ProgressCallback = _noop_progress,
) -> ResearchResult:
    """Run the full workflow and return the report plus its trace."""
    trace = RunTrace(topic=topic)

    def record(index: int, step: agents.StepOutput, seconds: float) -> None:
        trace.add_step(
            StepTrace(
                index=index,
                name=STEP_NAMES[index - 1],
                model=model,
                prompt=step.prompt,
                output=step.text,
                duration_seconds=round(seconds, 2),
                tool_calls=step.tool_calls,
            )
        )

    on_progress(1, TOTAL_STEPS, STEP_NAMES[0])
    plan, seconds = timed_call(agents.plan_research, topic, model=model)
    record(1, plan, seconds)

    on_progress(2, TOTAL_STEPS, STEP_NAMES[1])
    gathered, seconds = timed_call(
        agents.gather_sources, topic, plan.text, model=model
    )
    record(2, gathered, seconds)
    sources = agents.format_sources(gathered.tool_calls)

    on_progress(3, TOTAL_STEPS, STEP_NAMES[2])
    synthesis, seconds = timed_call(
        agents.synthesize, topic, gathered.text, sources, model=model
    )
    record(3, synthesis, seconds)

    on_progress(4, TOTAL_STEPS, STEP_NAMES[3])
    outline, seconds = timed_call(
        agents.write_outline, topic, synthesis.text, model=model
    )
    record(4, outline, seconds)

    on_progress(5, TOTAL_STEPS, STEP_NAMES[4])
    draft, seconds = timed_call(
        agents.write_draft, topic, outline.text, synthesis.text, sources, model=model
    )
    record(5, draft, seconds)

    on_progress(6, TOTAL_STEPS, STEP_NAMES[5])
    critique, seconds = timed_call(
        agents.critique, topic, draft.text, sources, model=model
    )
    record(6, critique, seconds)

    on_progress(7, TOTAL_STEPS, STEP_NAMES[6])
    final, seconds = timed_call(
        agents.revise, topic, draft.text, critique.text, sources, model=model
    )
    record(7, final, seconds)

    return ResearchResult(
        topic=topic,
        report=final.text,
        draft=draft.text,
        critique=critique.text,
        trace=trace,
        sources=sources,
    )


def save(result: ResearchResult) -> ResearchResult:
    """Write the report and trace to disk, filling in their paths."""
    slug = slugify(result.topic)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    trace_path = result.trace.save(TRACES_DIR, slug)
    report_path = REPORTS_DIR / f"{trace_path.stem}.md"

    header = f"# {result.topic}\n\n> 생성: {result.trace.started_at}\n\n---\n\n"
    report_path.write_text(header + result.report, encoding="utf-8")

    result.report_path = report_path
    result.trace_path = trace_path
    return result
