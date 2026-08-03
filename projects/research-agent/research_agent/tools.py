"""Research tools and the docstring-to-JSON-Schema conversion behind them.

The schema builder is the heart of the tool-use pattern: a plain Python
function plus its docstring is everything the model needs to call it. Whatever
you write in a docstring here is literally what the model reads, so treat the
descriptions as interface, not commentary.
"""

import inspect
import logging
import os
import xml.etree.ElementTree as ElementTree
from typing import Any, Callable
from urllib.parse import urlparse

import requests
import wikipedia
from docstring_parser import parse as parse_docstring
from tavily import TavilyClient

from .config import (
    ARXIV_API_URL,
    ARXIV_TIMEOUT_SECONDS,
    TAVILY_SEARCH_DEPTH,
    WIKIPEDIA_SENTENCES,
    has_tavily_key,
)

logger = logging.getLogger(__name__)

JSON_TYPE_BY_PYTHON_TYPE: dict[Any, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}
FALLBACK_JSON_TYPE = "string"

ARXIV_ATOM_NAMESPACE = {"atom": "http://www.w3.org/2005/Atom"}


def _json_type_of(annotation: Any) -> str:
    """Map a Python annotation to its JSON Schema type name."""
    origin = getattr(annotation, "__origin__", annotation)
    return JSON_TYPE_BY_PYTHON_TYPE.get(origin, FALLBACK_JSON_TYPE)


def build_tool_schema(fn: Callable) -> dict:
    """Build an OpenAI-style tool schema from a function's signature + docstring.

    This is what `docstring-parser` earns its place in requirements.txt for.
    """
    docstring = parse_docstring(fn.__doc__ or "")
    description_by_param = {p.arg_name: (p.description or "") for p in docstring.params}

    properties: dict[str, dict] = {}
    required: list[str] = []

    for name, param in inspect.signature(fn).parameters.items():
        properties[name] = {
            "type": _json_type_of(param.annotation),
            "description": description_by_param.get(name, ""),
        }
        is_optional = param.default is not inspect.Parameter.empty
        if not is_optional:
            required.append(name)

    summary = docstring.short_description or ""
    details = docstring.long_description or ""
    full_description = f"{summary}\n\n{details}".strip()

    return {
        "type": "function",
        "function": {
            "name": fn.__name__,
            "description": full_description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def domain_of(url: str) -> str:
    """Return the hostname of a URL, or an empty string when unparseable."""
    try:
        return urlparse(url).netloc
    except ValueError:
        # A malformed URL is not worth aborting a research run over.
        logger.warning("Could not parse URL for domain: %s", url)
        return ""


def search_wikipedia(query: str, max_results: int = 3) -> list[dict]:
    """Search Wikipedia for background, definitions, and historical context.

    Best for establishing foundational knowledge before looking at specialised
    sources. Returns an encyclopedic summary per matching article, not primary
    research. Use a short noun-phrase query rather than a full question.

    Args:
        query: Search phrase, e.g. "reusable launch vehicle economics".
        max_results: How many articles to summarise. Keep it small; 2-4 is usual.
    """
    try:
        titles = wikipedia.search(query, results=max_results)
    except Exception as error:
        # Network/parse failures are reported to the model rather than raised,
        # so one bad tool call does not kill the whole workflow.
        logger.warning("Wikipedia search failed for %r: %s", query, error)
        return [{"error": f"wikipedia search failed: {error}"}]

    results: list[dict] = []
    for title in titles:
        try:
            page = wikipedia.page(title, auto_suggest=False)
            summary = wikipedia.summary(
                title, sentences=WIKIPEDIA_SENTENCES, auto_suggest=False
            )
        except wikipedia.DisambiguationError as error:
            logger.info("Skipping ambiguous Wikipedia title %r: %s", title, error)
            continue
        except wikipedia.PageError:
            logger.info("Wikipedia page disappeared for title %r", title)
            continue

        results.append(
            {
                "title": page.title,
                "url": page.url,
                "snippet": summary,
                "source": "wikipedia",
            }
        )

    return results


def search_arxiv(query: str, max_results: int = 5) -> list[dict]:
    """Search arXiv for peer-reviewed and preprint academic papers.

    Best for technical evidence, theoretical frameworks, and recent research.
    Only covers computer science, mathematics, physics, statistics,
    quantitative biology, quantitative finance, electrical engineering, and
    economics. Do not use it for topics outside those fields.

    Args:
        query: Search phrase using technical terminology, e.g. "reflection agent LLM".
        max_results: How many papers to return. 3-8 is a reasonable range.
    """
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
    }

    try:
        response = requests.get(
            ARXIV_API_URL, params=params, timeout=ARXIV_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        feed = ElementTree.fromstring(response.content)
    except (requests.RequestException, ElementTree.ParseError) as error:
        logger.warning("arXiv search failed for %r: %s", query, error)
        return [{"error": f"arxiv search failed: {error}"}]

    results: list[dict] = []
    for entry in feed.findall("atom:entry", ARXIV_ATOM_NAMESPACE):
        title = entry.findtext("atom:title", default="", namespaces=ARXIV_ATOM_NAMESPACE)
        summary = entry.findtext(
            "atom:summary", default="", namespaces=ARXIV_ATOM_NAMESPACE
        )
        url = entry.findtext("atom:id", default="", namespaces=ARXIV_ATOM_NAMESPACE)
        published = entry.findtext(
            "atom:published", default="", namespaces=ARXIV_ATOM_NAMESPACE
        )
        authors = [
            author.findtext("atom:name", default="", namespaces=ARXIV_ATOM_NAMESPACE)
            for author in entry.findall("atom:author", ARXIV_ATOM_NAMESPACE)
        ]

        results.append(
            {
                "title": " ".join(title.split()),
                "url": url.strip(),
                "snippet": " ".join(summary.split()),
                "authors": authors,
                "published": published[:10],
                "source": "arxiv",
            }
        )

    return results


def search_web(query: str, max_results: int = 5) -> list[dict]:
    """Search the live web for current news, industry reports, and market information.

    Best for anything recent, commercial, or practical: company news, funding,
    product launches, market size, expert commentary, and blog posts. Returns
    extracted article text, not just links. Prefer this tool when the topic is
    not primarily academic or encyclopedic.

    Args:
        query: Natural-language search query, e.g. "small satellite launch market 2026".
        max_results: How many sources to return. 3-6 is a reasonable range.
    """
    try:
        client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        response = client.search(
            query=query,
            max_results=max_results,
            search_depth=TAVILY_SEARCH_DEPTH,
        )
    except Exception as error:
        # Surface the failure to the model instead of raising, so a single bad
        # query does not abort the run.
        logger.warning("Tavily search failed for %r: %s", query, error)
        return [{"error": f"web search failed: {error}"}]

    return [
        {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("content", ""),
            "source": "web",
        }
        for item in response.get("results", [])
    ]


# Registered tools. Adding another backend (DuckDuckGo, You.com, ...) means
# writing one function with a good docstring and appending it here — the schema,
# the prompt wiring, and the executor all pick it up automatically.
#
# search_web registers only when a key exists, so the agent degrades to
# Wikipedia + arXiv instead of failing when Tavily is not configured.
RESEARCH_TOOLS: list[Callable] = [search_wikipedia, search_arxiv]

if has_tavily_key():
    RESEARCH_TOOLS.insert(0, search_web)
else:
    logger.warning(
        "TAVILY_API_KEY not set — running without live web search. "
        "The agent will only see Wikipedia and arXiv."
    )

TOOL_BY_NAME: dict[str, Callable] = {fn.__name__: fn for fn in RESEARCH_TOOLS}

TOOL_SCHEMAS: list[dict] = [build_tool_schema(fn) for fn in RESEARCH_TOOLS]
