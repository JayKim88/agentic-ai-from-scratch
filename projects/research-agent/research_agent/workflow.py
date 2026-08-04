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

# Each step names itself and says which earlier outputs it consumes. Keeping
# that in one table means adding or reordering a step is a single edit, and no
# step index is written by hand — the previous version repeated the same
# progress/time/record trio seven times with literal indices.
#
# `needs` keys are looked up in a dict of everything produced so far, so a typo
# fails loudly at the first run rather than silently passing the wrong text.
STEPS: list[tuple[str, str, Callable, tuple[str, ...]]] = [
    ("plan", "리서치 계획 수립", agents.plan_research, ()),
    ("gathered", "자료 수집", agents.gather_sources, ("plan",)),
    ("synthesis", "종합·순위화", agents.synthesize, ("gathered", "sources")),
    ("outline", "아웃라인 작성", agents.write_outline, ("synthesis",)),
    ("draft", "초안 작성", agents.write_draft, ("outline", "synthesis", "sources")),
    ("critique", "비평 (반성)", agents.critique, ("draft", "sources")),
    ("report", "수정 → 최종 리포트", agents.revise, ("draft", "critique", "sources")),
]
TOTAL_STEPS = len(STEPS)
STEP_NAMES = [name for _, name, _, _ in STEPS]

# Produced mid-run rather than by a step, so it is seeded into the same lookup.
SOURCES_KEY = "sources"
GATHER_KEY = "gathered"


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
    produced: dict[str, str] = {}

    for index, (key, name, agent, needs) in enumerate(STEPS, start=1):
        on_progress(index, TOTAL_STEPS, name)

        arguments = [produced[dependency] for dependency in needs]
        step, seconds = timed_call(agent, topic, *arguments, model=model)

        trace.add_step(
            StepTrace(
                index=index,
                name=name,
                model=model,
                prompt=step.prompt,
                output=step.text,
                duration_seconds=round(seconds, 2),
                tool_calls=step.tool_calls,
                hit_turn_limit=step.hit_turn_limit,
            )
        )
        produced[key] = step.text

        # The numbered source list is derived from the gather step's tool calls
        # rather than its text, so it is not a step of its own.
        if key == GATHER_KEY:
            produced[SOURCES_KEY] = agents.format_sources(step.tool_calls)

    return ResearchResult(
        topic=topic,
        report=produced["report"],
        draft=produced["draft"],
        critique=produced["critique"],
        trace=trace,
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
