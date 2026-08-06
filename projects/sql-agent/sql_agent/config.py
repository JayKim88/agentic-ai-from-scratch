"""Model choices, temperatures, and API-key checks.

Model ids are `provider:model` strings so aisuite can route them and either
half can be swapped from the command line — the lab names that as an experiment
worth running rather than a setting to leave alone.

The temperatures are here rather than inline because they are what separates
the review conditions. The lab runs its text-only review at 0 and its
execution-feedback review at 1.0, so the two differ in more than the feedback;
`CONTROLLED_FEEDBACK_TEMPERATURE` exists to run the second one at 0 as well and
leave the execution result as the only difference.
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path

from dotenv import load_dotenv

# --- module state ---

_is_environment_loaded = False

# --- constants ---

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parents[1]

# Path arithmetic goes stale the moment the package moves, and the symptom
# would be a missing key rather than a missing directory.
REPO_ROOT_MARKER = "labs"

# The lab uses one model for both halves and says so explicitly:
# "openai:gpt-4.1 often gives the best results for self-reflection tasks".
DEFAULT_GENERATION_MODEL = "openai:gpt-4.1"
DEFAULT_EVALUATION_MODEL = "openai:gpt-4.1"

# The lab's values, kept as it sets them.
GENERATION_TEMPERATURE = 0.0
TEXT_REVIEW_TEMPERATURE = 0.0
EXTERNAL_FEEDBACK_TEMPERATURE = 1.0

# Ours: the execution-feedback review run at the text review's temperature, so
# a difference between the two can be attributed to the feedback itself.
CONTROLLED_FEEDBACK_TEMPERATURE = TEXT_REVIEW_TEMPERATURE

PROVIDER_SEPARATOR = ":"
ANTHROPIC_MARKERS = ("anthropic", "claude")

REQUIRED_KEY_BY_PROVIDER = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}

# Anthropic rejects a request without a token ceiling. A refined query plus a
# few sentences of feedback fits far inside this.
MAX_RESPONSE_TOKENS = 2048


# --- helpers ---


def _check_repo_root() -> None:
    """Fail loudly if `REPO_ROOT` no longer points at the repository."""
    if not (REPO_ROOT / REPO_ROOT_MARKER).exists():
        raise RuntimeError(
            f"REPO_ROOT resolved to {REPO_ROOT}, which has no {REPO_ROOT_MARKER}/ — "
            f"the package has moved and the path arithmetic in config.py is stale."
        )


def _provider_of(model: str) -> str:
    """The `provider` half of `provider:model`, or a guess from a bare name.

    Guessing is fine; guessing silently is not. A bare name that belongs to
    neither provider would otherwise sail past the key check and fail later
    with an unrelated error.
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
    """Read the repository-level .env. Safe to call more than once.

    Loads once per process: `require_key` runs before every model call, and a
    batch is hundreds of them, so re-reading the file each time would be pure
    waste. Values already in the environment win either way — that is dotenv's
    default — so re-reading would not pick up an edit made mid-run anyway.
    """
    global _is_environment_loaded
    if _is_environment_loaded:
        return

    _check_repo_root()
    load_dotenv(REPO_ROOT / ".env")
    _is_environment_loaded = True


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
        raise RuntimeError(
            f"{key_name} is not set — {model} needs it. Add it to {REPO_ROOT / '.env'}."
        )
