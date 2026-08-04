"""Model choices, shared constants, and API-key checks.

Model ids are `provider:model` strings so aisuite can route them, and so a run
can swap either half from the command line — the lab calls that out as an
experiment worth doing rather than a setting to leave alone.
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path

from dotenv import load_dotenv

# --- constants ---

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parents[1]

# Where a run leaves its output. Both are git-ignored.
CHARTS_DIR = PROJECT_ROOT / "charts"
TRACES_DIR = PROJECT_ROOT / "traces"

DEFAULT_IMAGE_BASENAME = "chart"

# Path arithmetic goes stale the moment the package moves, and the symptom would
# be a missing key rather than a missing directory. `_check_repo_root` turns
# that into an immediate, readable failure.
REPO_ROOT_MARKER = "labs"

# The lab pairs a fast model for drafting with a stronger one for reviewing.
# Its prose suggests gpt-4.1-mini and gpt-4.1; its code runs gpt-4o-mini and
# o4-mini. Both halves stay overridable.
DEFAULT_GENERATION_MODEL = "openai:gpt-4.1-mini"
DEFAULT_REFLECTION_MODEL = "openai:gpt-5"

# The lab lists Claude as a commented-out alternative for the reflection step.
# Keeping it reachable is not decoration: the two providers want different
# image payloads, so this is the only way to exercise that split.
ANTHROPIC_REFLECTION_MODEL = "anthropic:claude-sonnet-5"

PROVIDER_SEPARATOR = ":"
ANTHROPIC_MARKERS = ("anthropic", "claude")

# Anthropic requires an explicit token ceiling. Generated plotting code plus a
# critique fits well inside this.
MAX_RESPONSE_TOKENS = 4096


# Every chart the workflow writes. The lab fixes this in both prompts.
CHART_DPI = 300

REQUIRED_KEY_BY_PROVIDER = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


# --- helpers ---


def _check_repo_root() -> None:
    """Fail loudly if `REPO_ROOT` no longer points at the repository."""
    if not (REPO_ROOT / REPO_ROOT_MARKER).exists():
        raise RuntimeError(
            f"REPO_ROOT resolved to {REPO_ROOT}, which has no {REPO_ROOT_MARKER}/ — "
            f"the package has moved and the path arithmetic in config.py is stale."
        )


def _provider_of(model: str) -> str:
    """The `provider` half of `provider:model`, or a guess from the bare name.

    The lab passes bare names like "o4-mini" and sniffs for Claude, so bare
    names stay acceptable. But its guess is binary — anything not Claude is
    OpenAI — and a bare Mistral name would sail past the key check and fail
    later with an unrelated error. Guessing is fine; guessing silently is not.
    """
    if PROVIDER_SEPARATOR in model:
        return model.split(PROVIDER_SEPARATOR, 1)[0].strip().lower()

    lowered = model.lower()
    is_anthropic = any(marker in lowered for marker in ANTHROPIC_MARKERS)
    guess = "anthropic" if is_anthropic else "openai"

    warnings.warn(
        f"{model!r} has no provider prefix; assuming {guess!r}. "
        f"Write {guess}{PROVIDER_SEPARATOR}{model} to be explicit.",
        stacklevel=3,
    )
    return guess


# --- main export ---


def load_environment() -> None:
    """Read the repository-level .env. Safe to call more than once."""
    _check_repo_root()
    load_dotenv(REPO_ROOT / ".env")


def is_anthropic(model: str) -> bool:
    """Whether `model` should be addressed with Anthropic's message format."""
    return _provider_of(model) == "anthropic"


def require_key(model: str) -> None:
    """Fail early when the key for `model`'s provider is missing.

    Raises:
        RuntimeError: the provider is unknown, or its key is unset.
    """
    load_environment()
    provider = _provider_of(model)

    key_name = REQUIRED_KEY_BY_PROVIDER.get(provider)
    if key_name is None:
        known = ", ".join(sorted(REQUIRED_KEY_BY_PROVIDER))
        raise RuntimeError(f"unknown provider {provider!r} in model {model!r}. Known: {known}.")

    if not (os.getenv(key_name) or "").strip():
        raise RuntimeError(f"{key_name} is not set — {model} needs it. Add it to {REPO_ROOT / '.env'}.")
