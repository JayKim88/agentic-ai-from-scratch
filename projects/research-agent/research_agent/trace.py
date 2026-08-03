"""Per-step execution traces.

Module 1 lesson 6 makes the case for error analysis: to know *why* a workflow
underperforms you have to look at the intermediate output of every step, not
just the final report. That is only possible if the run recorded them, so
tracing is built in from the start rather than bolted on later.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

PREVIEW_CHAR_LIMIT = 400
TRACE_FILENAME_TIME_FORMAT = "%Y%m%d-%H%M%S"


def _preview(text: str) -> str:
    """Shorten text for at-a-glance reading in the saved trace."""
    if len(text) <= PREVIEW_CHAR_LIMIT:
        return text
    return f"{text[:PREVIEW_CHAR_LIMIT]}... [{len(text)} chars total]"


@dataclass
class ToolCallRecord:
    """One tool invocation: what the model asked for and what came back.

    `sources` keeps {title, url} pairs rather than bare URLs so the report's
    References section can name what it cites.
    """

    name: str
    arguments: dict[str, Any]
    result_count: int
    sources: list[dict[str, str]]
    result_preview: str
    failed: bool = False

    @property
    def urls(self) -> list[str]:
        return [source["url"] for source in self.sources if source.get("url")]


@dataclass
class StepTrace:
    """One workflow step, with everything needed to diagnose it after the fact."""

    index: int
    name: str
    model: str
    prompt: str
    output: str
    duration_seconds: float
    tool_calls: list[ToolCallRecord] = field(default_factory=list)


@dataclass
class RunTrace:
    """The full record of one research run."""

    topic: str
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    steps: list[StepTrace] = field(default_factory=list)

    def add_step(self, step: StepTrace) -> None:
        self.steps.append(step)

    def collected_urls(self) -> set[str]:
        """Every URL any tool actually returned during this run.

        This is the ground truth the citation-grounding eval compares the final
        report against: a URL in the report that is not in this set was invented.
        """
        return {
            url
            for step in self.steps
            for call in step.tool_calls
            for url in call.urls
            if url
        }

    def total_tool_calls(self) -> int:
        return sum(len(step.tool_calls) for step in self.steps)

    def total_duration_seconds(self) -> float:
        return sum(step.duration_seconds for step in self.steps)

    def to_dict(self) -> dict:
        payload = asdict(self)
        # Long prompts and outputs make the file unreadable; keep both a preview
        # and the full text so the trace stays browsable but lossless.
        for step, raw in zip(payload["steps"], self.steps):
            step["prompt_preview"] = _preview(raw.prompt)
            step["output_preview"] = _preview(raw.output)
        payload["summary"] = {
            "steps": len(self.steps),
            "tool_calls": self.total_tool_calls(),
            "unique_urls": len(self.collected_urls()),
            "duration_seconds": round(self.total_duration_seconds(), 1),
        }
        return payload

    def save(self, directory: Path, slug: str) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime(TRACE_FILENAME_TIME_FORMAT)
        path = directory / f"{timestamp}-{slug}.json"
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return path
