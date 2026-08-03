"""Configuration and shared constants for the research agent."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = PROJECT_ROOT / "reports"
TRACES_DIR = PROJECT_ROOT / "traces"

# Model routing. aisuite resolves the "provider:model" prefix, so swapping a
# provider later means changing these strings and nothing else.
DEFAULT_MODEL = "openai:gpt-4.1-mini"
EDITOR_MODEL = "openai:gpt-4.1-mini"

# The research step is the only one that calls tools; every other step is a
# single completion, so the loop cap only applies there.
MAX_TOOL_TURNS = 5
MAX_TOOL_CALLS_PER_TURN = 4

# Deterministic everywhere except the draft, where a little variety helps.
TEMPERATURE_ANALYTICAL = 0.0
TEMPERATURE_DRAFTING = 0.4

WIKIPEDIA_SENTENCES = 5
ARXIV_API_URL = "http://export.arxiv.org/api/query"
ARXIV_TIMEOUT_SECONDS = 30

# "basic" costs 1 Tavily credit per call, "advanced" costs 2. The free tier
# gives 1,000 credits/month, so basic keeps a full run well under 10 credits.
TAVILY_SEARCH_DEPTH = "basic"

REPORT_MIN_WORDS = 400


def has_tavily_key() -> bool:
    """Whether live web search is available.

    Tavily is optional: without it the agent still runs on Wikipedia + arXiv,
    it just cannot reach current news or industry sources.
    """
    return bool(os.getenv("TAVILY_API_KEY"))


def require_openai_key() -> str:
    """Return the OpenAI API key, failing loudly when it is missing.

    A missing key surfaces as an opaque auth error deep inside the SDK, so we
    check once up front instead.
    """
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Create a .env file at the project root "
            "with OPENAI_API_KEY=sk-... before running the agent."
        )
    return key
