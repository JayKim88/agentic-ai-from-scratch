"""Optional on-disk cache for tool results.

Tuning prompts means running the same topic repeatedly, and every run re-issues
the same searches and re-downloads the same PDFs — about a fifth of the wall
clock, plus Tavily credits, spent re-fetching identical data.

Off by default and enabled per run, because a cached run is not a fresh research
run: nothing that reports on current events should silently serve yesterday's
search results. When it is on, every hit is logged so the trace of what happened
stays honest.
"""

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 24 * 60 * 60
CACHE_KEY_LENGTH = 16

_directory: Path | None = None


def enable(directory: Path) -> None:
    """Turn caching on for this process and create the directory if needed."""
    global _directory
    directory.mkdir(parents=True, exist_ok=True)
    _directory = directory
    logger.info("Tool cache enabled at %s", directory)


def is_enabled() -> bool:
    return _directory is not None


def _path_for(tool_name: str, arguments: dict) -> Path:
    """Hash the call into a filename, sorting keys so argument order cannot matter."""
    payload = json.dumps({"tool": tool_name, "args": arguments}, sort_keys=True)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:CACHE_KEY_LENGTH]
    return _directory / f"{tool_name}-{digest}.json"


def get(tool_name: str, arguments: dict) -> Any | None:
    """Return a cached result, or None when absent, stale, or unreadable."""
    if not is_enabled():
        return None

    path = _path_for(tool_name, arguments)
    if not path.exists():
        return None

    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        logger.warning("Ignoring unreadable cache entry %s: %s", path.name, error)
        return None

    age_seconds = time.time() - entry.get("stored_at", 0)
    if age_seconds > CACHE_TTL_SECONDS:
        logger.info("Cache entry for %s expired (%.0fh old)", tool_name, age_seconds / 3600)
        return None

    logger.info("Cache hit for %s(%s)", tool_name, arguments)
    return entry.get("result")


def put(tool_name: str, arguments: dict, result: Any) -> None:
    """Store a successful result. Failures are never cached."""
    if not is_enabled():
        return

    is_failure = isinstance(result, dict) and "error" in result
    if is_failure:
        return

    entry = {"stored_at": time.time(), "tool": tool_name, "args": arguments, "result": result}
    path = _path_for(tool_name, arguments)
    try:
        path.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")
    except OSError as error:
        # A cache we cannot write to is a slow run, not a broken one.
        logger.warning("Could not write cache entry %s: %s", path.name, error)
