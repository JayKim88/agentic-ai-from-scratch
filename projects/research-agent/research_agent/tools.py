"""Research tools and the docstring-to-JSON-Schema conversion behind them.

The schema builder is the heart of the tool-use pattern: a plain Python
function plus its docstring is everything the model needs to call it. Whatever
you write in a docstring here is literally what the model reads, so treat the
descriptions as interface, not commentary.
"""

import inspect
import io
import logging
import os
import time
import xml.etree.ElementTree as ElementTree
from typing import Any, Callable
from urllib.parse import urlparse

import requests
import wikipedia
from docstring_parser import parse as parse_docstring
from pdfminer.high_level import extract_text
from tavily import TavilyClient

from .config import (
    ARXIV_API_URL,
    ARXIV_PDF_DELAY_SECONDS,
    ARXIV_PDF_FETCH_LIMIT,
    ARXIV_PDF_MAX_CHARS,
    ARXIV_PDF_MAX_PAGES,
    ARXIV_PDF_TIMEOUT_SECONDS,
    ARXIV_TIMEOUT_SECONDS,
    HTTP_USER_AGENT,
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


def _fetch_paper_fulltext(abstract_url: str) -> str:
    """Download an arXiv paper and extract its opening pages as plain text.

    Returns an empty string on any failure — the caller keeps the abstract in
    that case, so a paywalled or malformed PDF degrades the result instead of
    breaking the search.
    """
    pdf_url = abstract_url.replace("/abs/", "/pdf/")
    try:
        response = requests.get(
            pdf_url,
            timeout=ARXIV_PDF_TIMEOUT_SECONDS,
            headers={"User-Agent": HTTP_USER_AGENT},
        )
        response.raise_for_status()
        text = extract_text(
            io.BytesIO(response.content), maxpages=ARXIV_PDF_MAX_PAGES
        )
    except requests.RequestException as error:
        logger.warning("Could not download %s: %s", pdf_url, error)
        return ""
    except Exception as error:
        # pdfminer raises a wide range of parse errors on malformed PDFs.
        logger.warning("Could not extract text from %s: %s", pdf_url, error)
        return ""

    return " ".join(text.split())[:ARXIV_PDF_MAX_CHARS]


def _add_fulltext(papers: list[dict]) -> None:
    """Upgrade the top papers from abstract to full text, in place.

    Only the first few are fetched: downloading and parsing a PDF costs several
    seconds, and the model usually only cites the leading results anyway.
    """
    for position, paper in enumerate(papers[:ARXIV_PDF_FETCH_LIMIT]):
        is_after_first = position > 0
        if is_after_first:
            time.sleep(ARXIV_PDF_DELAY_SECONDS)

        full_text = _fetch_paper_fulltext(paper["url"])
        if not full_text:
            continue

        paper["snippet"] = full_text
        paper["snippet_source"] = "pdf_fulltext"


def _entry_text(entry: ElementTree.Element, tag: str) -> str:
    """Read one Atom child element, collapsing the whitespace arXiv pads it with."""
    raw = entry.findtext(f"atom:{tag}", default="", namespaces=ARXIV_ATOM_NAMESPACE)
    return " ".join(raw.split())


def _paper_from(entry: ElementTree.Element) -> dict:
    """Convert one Atom entry into the shape every search tool returns."""
    return {
        "title": _entry_text(entry, "title"),
        "url": _entry_text(entry, "id"),
        "snippet": _entry_text(entry, "summary"),
        "snippet_source": "abstract",
        "authors": [
            _entry_text(author, "name")
            for author in entry.findall("atom:author", ARXIV_ATOM_NAMESPACE)
        ],
        "published": _entry_text(entry, "published")[:10],
        "source": "arxiv",
    }


def _query_arxiv(search_query: str, max_results: int) -> list[dict] | None:
    """Run one arXiv API query and parse the Atom feed.

    Returns None when the request or parse failed, an empty list when the query
    simply matched nothing — the caller needs to tell those two apart.
    """
    params = {"search_query": search_query, "start": 0, "max_results": max_results}

    try:
        response = requests.get(
            ARXIV_API_URL, params=params, timeout=ARXIV_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        feed = ElementTree.fromstring(response.content)
    except (requests.RequestException, ElementTree.ParseError) as error:
        logger.warning("arXiv query failed for %r: %s", search_query, error)
        return None

    return [_paper_from(entry) for entry in feed.findall("atom:entry", ARXIV_ATOM_NAMESPACE)]


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


def search_arxiv(query: str, max_results: int = 5, category: str = "") -> list[dict]:
    """Search arXiv for peer-reviewed and preprint academic papers.

    Best for technical evidence, theoretical frameworks, and recent research.
    For the top results this returns the paper's opening pages, not just the
    abstract, so specific figures and experimental details are available to
    cite. Only covers computer science, mathematics, physics, statistics,
    quantitative biology, quantitative finance, electrical engineering, and
    economics. Do not use it for topics outside those fields.

    Args:
        query: Search phrase using technical terminology, e.g. "reflection agent LLM".
        max_results: How many papers to return. 3-8 is a reasonable range.
        category: arXiv category to restrict the search to. Strongly recommended
            — without it, keyword matches from unrelated fields dominate, so a
            query about "error correction" in AI returns quantum computing
            papers. Common values: cs.AI (artificial intelligence), cs.CL
            (language and NLP), cs.LG (machine learning), cs.SE (software
            engineering), cs.CV (vision), cs.RO (robotics), stat.ML, math.OC
            (optimisation), q-bio, q-fin, econ.EM, eess.SY.
    """
    scope = category.strip()
    search_query = f"all:{query} AND cat:{scope}" if scope else f"all:{query}"

    papers = _query_arxiv(search_query, max_results)
    if papers is None:
        return [{"error": "arxiv search failed"}]

    # arXiv does not apply this AND strictly: `all:x AND cat:bogus` still
    # returns tens of thousands of hits, so `cat:` biases the ranking rather
    # than filtering. Measured effect is still large — scoping a query about
    # "error correction" to cs.AI drops the quantum-computing papers that
    # otherwise take the top slots. Quoting the query would make AND strict but
    # then demands a verbatim phrase match, which returns nothing.
    #
    # A genuinely narrow query can still come back empty, and an empty result
    # reads to the model as "no such research exists", so retry unscoped.
    found_nothing_while_scoped = not papers and bool(scope)
    if found_nothing_while_scoped:
        logger.info("No arXiv results in category %r; retrying unscoped", scope)
        papers = _query_arxiv(f"all:{query}", max_results) or []

    _add_fulltext(papers)
    return papers


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
