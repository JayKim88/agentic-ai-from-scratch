"""Objective evaluations for a finished run.

Module 1 lesson 6 argued for evals you can compute rather than judge: the
competitor-mention example works because a name is either present or it is not.
Everything here follows that shape — countable, binary, no LLM in the loop.

The headline metric is citation grounding: a URL that appears in the report but
never came back from a tool was invented by the model.
"""

import difflib
import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

import requests
import textstat

from .config import REPORT_MIN_WORDS
from .workflow import ResearchResult

logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(r"https?://[^\s<>\"'\)\]]+")
TRAILING_PUNCTUATION = ".,;:!?"

REFERENCES_HEADING_PATTERN = re.compile(r"^#{1,4}\s*references\b", re.IGNORECASE | re.MULTILINE)

MIN_SOURCE_DOMAINS = 3
MIN_READABILITY_SCORE = 20.0

MAX_LINKS_TO_CHECK = 15
LINK_CHECK_TIMEOUT_SECONDS = 8
# Bare HEAD requests get 403'd by a lot of sites — even Wikipedia — so the
# check would report live pages as broken. Use GET with a browser UA instead.
LINK_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
# "We were refused" is not "the page is gone". Only the second is a defect in
# the report, so only the second fails the check.
BLOCKED_STATUS_CODES = frozenset({401, 403, 405, 429})
DEAD_STATUS_CODES = frozenset({404, 410})
# Above this similarity the revision changed essentially nothing, which means
# the reflection step earned nothing for its two extra model calls.
MAX_DRAFT_SIMILARITY = 0.98


@dataclass
class Check:
    """One evaluation outcome."""

    name: str
    passed: bool
    value: str
    detail: str = ""


@dataclass
class EvalReport:
    checks: list[Check] = field(default_factory=list)

    @property
    def passed_count(self) -> int:
        return sum(1 for check in self.checks if check.passed)

    @property
    def all_passed(self) -> bool:
        return all(check.passed for check in self.checks)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed_count,
            "total": len(self.checks),
            "checks": [vars(check) for check in self.checks],
        }


def _normalize_url(url: str) -> str:
    """Strip scheme, trailing slash, and trailing punctuation for comparison.

    arXiv hands back `http://arxiv.org/abs/...` while models habitually write
    `https://`, so comparing raw strings would report false fabrications.
    """
    cleaned = url.rstrip(TRAILING_PUNCTUATION).rstrip("/")
    without_scheme = re.sub(r"^https?://", "", cleaned, flags=re.IGNORECASE)
    return without_scheme.lower()


def extract_urls(text: str) -> list[str]:
    """Every URL appearing in the text, in order, deduplicated."""
    seen: set[str] = set()
    urls: list[str] = []
    for match in URL_PATTERN.findall(text):
        url = match.rstrip(TRAILING_PUNCTUATION)
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def check_citation_grounding(result: ResearchResult) -> Check:
    """THE metric: is every URL in the report one a tool actually returned?"""
    collected = {_normalize_url(url) for url in result.trace.collected_urls()}
    cited = extract_urls(result.report)

    fabricated = [url for url in cited if _normalize_url(url) not in collected]
    grounded_count = len(cited) - len(fabricated)

    detail = ""
    if fabricated:
        detail = "지어낸 URL: " + ", ".join(fabricated[:5])

    return Check(
        name="인용 정합성",
        passed=not fabricated and bool(cited),
        value=f"{grounded_count}/{len(cited)}",
        detail=detail or ("리포트에 URL이 없음" if not cited else ""),
    )


def check_references_section(result: ResearchResult) -> Check:
    found = bool(REFERENCES_HEADING_PATTERN.search(result.report))
    return Check(
        name="References 섹션",
        passed=found,
        value="있음" if found else "없음",
    )


def check_source_diversity(result: ResearchResult) -> Check:
    domains = {urlparse(url).netloc for url in extract_urls(result.report)}
    domains.discard("")
    return Check(
        name="소스 다양성",
        passed=len(domains) >= MIN_SOURCE_DOMAINS,
        value=f"{len(domains)}개 도메인",
        detail=f"기준 {MIN_SOURCE_DOMAINS}개 이상",
    )


def check_word_count(result: ResearchResult) -> Check:
    words = len(result.report.split())
    return Check(
        name="분량",
        passed=words >= REPORT_MIN_WORDS,
        value=f"{words} 단어",
        detail=f"기준 {REPORT_MIN_WORDS} 이상",
    )


def check_readability(result: ResearchResult) -> Check:
    """Score the prose only.

    A References section is a list of long URLs, not prose; leaving it in costs
    roughly six Flesch points and measures the wrong thing.
    """
    body = REFERENCES_HEADING_PATTERN.split(result.report)[0]
    score = textstat.flesch_reading_ease(body)
    return Check(
        name="가독성 (Flesch)",
        passed=score >= MIN_READABILITY_SCORE,
        value=f"{score:.1f}",
        detail=f"기준 {MIN_READABILITY_SCORE} 이상 (본문만, References 제외)",
    )


def check_tool_usage(result: ResearchResult) -> Check:
    """A run that never called a tool answered from model memory, not research."""
    calls = result.trace.total_tool_calls()
    failed = sum(
        1 for step in result.trace.steps for call in step.tool_calls if call.failed
    )
    return Check(
        name="도구 사용",
        passed=calls > 0 and failed == 0,
        value=f"{calls}회",
        detail=f"실패 {failed}회" if failed else "",
    )


def check_reflection_effect(result: ResearchResult) -> Check:
    """Did critique + revise actually change the draft?

    If the final report is nearly identical to the draft, the reflection pattern
    is costing two model calls and returning nothing.
    """
    similarity = difflib.SequenceMatcher(None, result.draft, result.report).ratio()
    return Check(
        name="반성 효과",
        passed=similarity < MAX_DRAFT_SIMILARITY,
        value=f"초안 대비 {similarity:.1%} 동일",
        detail=f"{MAX_DRAFT_SIMILARITY:.0%} 이상 동일하면 반성이 무의미",
    )


def _classify_link(url: str) -> str:
    """Return one of: alive, blocked, dead, unreachable."""
    try:
        response = requests.get(
            url,
            timeout=LINK_CHECK_TIMEOUT_SECONDS,
            allow_redirects=True,
            headers={"User-Agent": LINK_USER_AGENT},
            stream=True,  # headers only; we never read the body
        )
        response.close()
    except requests.RequestException as error:
        logger.info("Link unreachable: %s (%s)", url, error)
        return "unreachable"

    if response.status_code < 400:
        return "alive"
    if response.status_code in BLOCKED_STATUS_CODES:
        return "blocked"
    if response.status_code in DEAD_STATUS_CODES:
        return "dead"
    logger.info("Link returned %s: %s", response.status_code, url)
    return "dead"


def check_link_liveness(result: ResearchResult) -> Check:
    """Fetch cited URLs and separate broken links from merely blocked ones.

    Only a genuinely missing page (404/410) counts as a failure — a 403 from a
    paywall means the citation is unverifiable, not wrong.
    """
    urls = extract_urls(result.report)[:MAX_LINKS_TO_CHECK]
    if not urls:
        return Check(name="링크 유효성", passed=False, value="확인할 링크 없음")

    tally = {"alive": 0, "blocked": 0, "dead": 0, "unreachable": 0}
    for url in urls:
        tally[_classify_link(url)] += 1

    return Check(
        name="링크 유효성",
        passed=tally["dead"] == 0,
        value=f"{tally['alive']}/{len(urls)} 정상",
        detail=(
            f"차단 {tally['blocked']} · 끊김 {tally['dead']} · 응답없음 {tally['unreachable']}"
        ),
    )


def evaluate(result: ResearchResult, check_links: bool = True) -> EvalReport:
    """Run every check. Link checking is separated because it hits the network."""
    checks = [
        check_citation_grounding(result),
        check_references_section(result),
        check_tool_usage(result),
        check_source_diversity(result),
        check_word_count(result),
        check_reflection_effect(result),
        check_readability(result),
    ]
    if check_links:
        checks.append(check_link_liveness(result))
    return EvalReport(checks=checks)
