"""The seven workflow steps, each one a prompt plus a model call.

Steps 5-7 (draft, critique, revise) are the reflection pattern: module 1 showed
that splitting "write the essay" into draft / find what needs fixing / revise is
what lifted the essay workflow from "still not good enough" to acceptable.

Every step returns its prompt alongside its output so the trace can show what
was actually asked, not just what came back.
"""

from dataclasses import dataclass, field

from .config import (
    DEFAULT_MODEL,
    EDITOR_MODEL,
    REPORT_MIN_WORDS,
    TEMPERATURE_ANALYTICAL,
    TEMPERATURE_DRAFTING,
)
from .llm import complete, run_tool_loop
from .trace import ToolCallRecord

SOURCE_LINE_LIMIT = 40

# Repeated in three prompts, so it lives in one place. Grounding every citation
# in the numbered list is what makes the citation-grounding eval meaningful:
# a URL the model invents will not appear in the collected sources.
CITATION_RULES = """Citation rules:
- Cite inline with bracketed numbers matching the source list, e.g. [3].
- Use ONLY sources from the list. Never invent a URL, title, or statistic.
- If the sources do not cover something, say so explicitly instead of guessing.
- End with a "## References" section listing every cited source as: [n] Title - URL"""

# Added after the first run scored -3.5 on Flesch reading ease: the model
# defaults to 40-word sentences stacked with subordinate clauses. Readability
# is one of the evals, so the constraint belongs in the prompt.
PROSE_RULES = """Prose rules:
- Keep sentences under 25 words. Break long ones into two.
- One idea per sentence. Avoid stacking subordinate clauses.
- Prefer plain verbs over nominalisations ("we tested" over "testing was performed").
- Cut hedging and filler. Every sentence must carry information."""


@dataclass
class StepOutput:
    """What one step produced, plus the prompt that produced it."""

    prompt: str
    text: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    hit_turn_limit: bool = False


def format_sources(tool_calls: list[ToolCallRecord]) -> str:
    """Render collected sources as a numbered list the model can cite from.

    Deduplicated by URL, because the same page often comes back from more than
    one search.
    """
    lines: list[str] = []
    seen_urls: set[str] = set()

    for call in tool_calls:
        for source in call.sources:
            url = source.get("url", "")
            is_new = url and url not in seen_urls
            if not is_new:
                continue
            seen_urls.add(url)
            title = source.get("title") or "(untitled)"
            lines.append(f"[{len(lines) + 1}] {title} - {url}")

    if not lines:
        return "(no sources were collected)"
    return "\n".join(lines[:SOURCE_LINE_LIMIT])


def plan_research(topic: str, model: str = DEFAULT_MODEL) -> StepOutput:
    """Step 1 — decide what needs to be found out before writing anything."""
    prompt = f"""You are planning a research report on the topic below.

List 4-6 specific questions that the report must answer to be genuinely useful.
Focus on what a knowledgeable reader would actually want to know: mechanisms,
numbers, trade-offs, and current state of play. Avoid generic questions.

Output the questions as a plain numbered list and nothing else.

Topic: {topic}"""
    return StepOutput(prompt=prompt, text=complete(prompt, model=model))


def gather_sources(
    topic: str, plan: str, model: str = DEFAULT_MODEL
) -> StepOutput:
    """Step 2 — the only step with tools. The model chooses what to search."""
    prompt = f"""You are a research assistant gathering evidence for a report.

Use your search tools to answer the research questions below. Choose tools that
fit the topic: live web search for current or commercial information, Wikipedia
for background and definitions, arXiv for technical and academic evidence.
Run several searches with different phrasings rather than one broad search.

When you are done, summarise what you found. For each finding, state the claim
and the URL it came from. Do not write the report yet.

Topic: {topic}

Research questions:
{plan}"""

    result = run_tool_loop(prompt, model=model)
    return StepOutput(
        prompt=prompt,
        text=result.content,
        tool_calls=result.tool_calls,
        hit_turn_limit=result.hit_turn_limit,
    )


def synthesize(
    topic: str, findings: str, sources: str, model: str = DEFAULT_MODEL
) -> StepOutput:
    """Step 3 — rank, deduplicate, and note what the evidence does not cover."""
    prompt = f"""Organise the research findings below into evidence for a report.

Do this:
1. Group the findings by theme.
2. Within each theme, order by how well supported and how recent the evidence is.
3. Remove duplicates and anything not backed by a source.
4. End with a short "Gaps" section naming what the sources fail to answer.

Keep the bracketed source numbers attached to every claim.

Topic: {topic}

Sources:
{sources}

Findings:
{findings}"""
    return StepOutput(prompt=prompt, text=complete(prompt, model=model))


def write_outline(
    topic: str, synthesis: str, model: str = DEFAULT_MODEL
) -> StepOutput:
    """Step 4 — structure before prose, so the draft has somewhere to go."""
    prompt = f"""Write an outline for a research report on the topic below.

Use the synthesised evidence to decide the sections. Give each section a
heading and 2-4 bullet points naming what it will argue and which source
numbers support it. Include an introduction and a conclusion.

Output the outline only.

Topic: {topic}

Evidence:
{synthesis}"""
    return StepOutput(prompt=prompt, text=complete(prompt, model=model))


def write_draft(
    topic: str,
    outline: str,
    synthesis: str,
    sources: str,
    model: str = DEFAULT_MODEL,
) -> StepOutput:
    """Step 5 — first draft. Deliberately not the final answer."""
    prompt = f"""Write a research report in Markdown following the outline below.

Requirements:
- At least {REPORT_MIN_WORDS} words.
- Follow the outline's section structure.
- Ground every factual claim in the evidence provided.

{PROSE_RULES}

{CITATION_RULES}

Topic: {topic}

Outline:
{outline}

Evidence:
{synthesis}

Sources:
{sources}"""
    return StepOutput(
        prompt=prompt,
        text=complete(prompt, model=model, temperature=TEMPERATURE_DRAFTING),
    )


def critique(
    topic: str, draft: str, sources: str, model: str = EDITOR_MODEL
) -> StepOutput:
    """Step 6 — reflection. Find the problems; do not fix them yet.

    Separating "what is wrong" from "fix it" is the point of the pattern. Asking
    for both at once tends to produce a lightly reworded draft.
    """
    prompt = f"""You are an exacting editor reviewing the draft report below.

Do NOT rewrite it. List concrete problems only, ordered by severity, as a
numbered list. For each, quote the offending text and say what is wrong.

Check specifically for:
- Claims with no citation, or citations pointing to sources that cannot support them.
- URLs or numbers that do not appear in the source list (these are fabrications).
- Sections that restate each other.
- Vague filler that carries no information.
- Sentences longer than 25 words, or sentences stacking three or more clauses.
- Missing or malformed References section.

If a section is genuinely fine, do not invent a problem for it.

Topic: {topic}

Sources:
{sources}

Draft:
{draft}"""
    return StepOutput(prompt=prompt, text=complete(prompt, model=model))


def revise(
    topic: str,
    draft: str,
    critique_text: str,
    sources: str,
    model: str = DEFAULT_MODEL,
) -> StepOutput:
    """Step 7 — apply the critique and emit the final report."""
    prompt = f"""Revise the draft report below by addressing every point in the critique.

Rules:
- Fix each numbered issue. Do not ignore any.
- Delete unsupported claims rather than adding citations that do not support them.
- Keep everything that was already good; this is a revision, not a rewrite.
- Output the complete final report in Markdown and nothing else.

{PROSE_RULES}

{CITATION_RULES}

Topic: {topic}

Sources:
{sources}

Critique:
{critique_text}

Draft:
{draft}"""
    return StepOutput(
        prompt=prompt,
        text=complete(prompt, model=model, temperature=TEMPERATURE_ANALYTICAL),
    )
