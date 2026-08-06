"""Record what each step did, so a run can be read back afterwards.

Nothing in the lab corresponds to this. It exists because a success rate on its
own does not say what produced it — which model, at what temperature, whether
the review parsed, how far off a wrong answer was. Those are the questions that
come up the moment two conditions differ.
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# --- types ---


@dataclass
class StepRecord:
    """One step of the workflow."""

    name: str
    model: str | None = None
    duration_seconds: float = 0.0
    detail: dict = field(default_factory=dict)


@dataclass
class RunTrace:
    """Everything one invocation did."""

    question: str
    condition: str
    generation_model: str
    evaluation_model: str
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    steps: list[StepRecord] = field(default_factory=list)

    @contextmanager
    def timed(self, name: str, model: str | None = None):
        """Time a step and record it, whether or not it succeeds.

        Yields the record so the caller can fill in `detail` once it knows it.
        Recording on the way out rather than on success means a step that raised
        still appears — otherwise the one step worth investigating is the one
        missing from the trace.
        """
        record = StepRecord(name=name, model=model)
        started = time.perf_counter()
        try:
            yield record
        finally:
            record.duration_seconds = round(time.perf_counter() - started, 2)
            self.steps.append(record)

    @property
    def total_seconds(self) -> float:
        return round(sum(step.duration_seconds for step in self.steps), 2)

    def save(self, path: str | Path) -> Path:
        """Write the trace as JSON beside the run's other output."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        return path
