"""Record what each step did, so a run can be read back afterwards.

Nothing in the lab corresponds to this. It exists because the charts alone do
not say which model produced them, how long it took, or whether the critique
parsed cleanly — and those are the questions the completion criteria ask.
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
    artifact: str | None = None
    detail: dict = field(default_factory=dict)


@dataclass
class RunTrace:
    """Everything one invocation did."""

    instruction: str
    generation_model: str
    reflection_model: str
    dataset_path: str
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    steps: list[StepRecord] = field(default_factory=list)

    @contextmanager
    def timed(self, name: str, model: str | None = None):
        """Time a step and record it, whether or not it succeeds.

        Yields the record so the caller can fill in `artifact` and `detail`
        once it knows them. Recording on the way out rather than on success
        means a step that raised still appears in the trace — otherwise the one
        step worth investigating is the one missing from it.
        """
        record = StepRecord(name=name, model=model)
        started = time.perf_counter()
        try:
            yield record
        finally:
            record.duration_seconds = round(time.perf_counter() - started, 2)
            self.steps.append(record)

    def save(self, path: str | Path) -> Path:
        """Write the trace as JSON beside the run's other output."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        return target
