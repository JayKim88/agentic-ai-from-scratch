"""LLM access and the hand-written tool-calling loop.

The loop below is the point of this project. aisuite can run it for you by
passing callables plus `max_turns`, but then the mechanism stays a black box.
Here every turn is explicit: send schemas, read `tool_calls`, execute them,
feed the results back as `role: "tool"` messages, repeat.

Note that we deliberately never pass `max_turns` to aisuite — that is the flag
that switches on its automatic executor (aisuite/client.py, `_chat_completion_with_tools`).
Without it, `tools` is forwarded to the provider untouched.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import aisuite

from . import cache
from .config import (
    DEFAULT_MODEL,
    MAX_TOOL_TURNS,
    TEMPERATURE_ANALYTICAL,
    require_openai_key,
)
from .tools import TOOL_BY_NAME, TOOL_SCHEMAS
from .trace import ToolCallRecord

logger = logging.getLogger(__name__)

ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
ROLE_TOOL = "tool"

TOOL_RESULT_PREVIEW_CHARS = 300
FORCE_ANSWER_PROMPT = (
    "Stop searching and answer now using only what you have gathered so far."
)

_client: aisuite.Client | None = None


@dataclass
class ToolLoopResult:
    """Final answer plus the audit trail of how the model got there."""

    content: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    turns: int = 0
    hit_turn_limit: bool = False


def _get_client() -> aisuite.Client:
    """Return a lazily created aisuite client, validating credentials once."""
    global _client
    if _client is None:
        require_openai_key()
        _client = aisuite.Client()
    return _client


def _parse_arguments(raw: str | None) -> tuple[dict, str]:
    """Parse tool-call arguments. Returns (arguments, error) with error empty on success."""
    try:
        return json.loads(raw or "{}"), ""
    except json.JSONDecodeError as error:
        return {}, f"malformed arguments: {error}"


def _execute_tool(name: str, arguments: dict) -> tuple[Any, bool]:
    """Run one tool. Returns (result, failed).

    Caching sits here rather than inside each tool, so the tools stay pure and
    all three are covered by one code path.

    Failures come back as data rather than exceptions: the model gets to see the
    error message and can recover by calling a different tool.
    """
    tool = TOOL_BY_NAME.get(name)
    if tool is None:
        logger.error("Model requested unknown tool %r", name)
        return {"error": f"unknown tool: {name}"}, True

    cached = cache.get(name, arguments)
    if cached is not None:
        return cached, False

    logger.info("Calling %s(%s)", name, arguments)
    try:
        result = tool(**arguments)
    except TypeError as error:
        # Wrong or missing parameters — a schema/model mismatch worth surfacing.
        logger.error("Bad call signature for %s: %s", name, error)
        return {"error": f"invalid arguments for {name}: {error}"}, True

    cache.put(name, arguments, result)
    return result, False


def _sources_in(result: Any) -> list[dict[str, str]]:
    """Collect {title, url} pairs from a tool result.

    This is what the citation-grounding eval later compares the report against,
    so it has to capture every source the model was actually shown.
    """
    if not isinstance(result, list):
        return []
    return [
        {"title": item.get("title", ""), "url": item["url"]}
        for item in result
        if isinstance(item, dict) and item.get("url")
    ]


def _record_of(name: str, arguments: dict, result: Any, failed: bool) -> ToolCallRecord:
    return ToolCallRecord(
        name=name,
        arguments=arguments,
        result_count=len(result) if isinstance(result, list) else 1,
        sources=_sources_in(result),
        result_preview=json.dumps(result, ensure_ascii=False, default=str)[
            :TOOL_RESULT_PREVIEW_CHARS
        ],
        failed=failed,
    )


def _assistant_message_from(message: Any) -> dict:
    """Rebuild the assistant turn as a plain dict.

    Provider SDKs return objects, but the next request needs JSON-serialisable
    messages, and tool_calls must be echoed back verbatim so the model can match
    each result to the request id that produced it.
    """
    return {
        "role": ROLE_ASSISTANT,
        "content": message.content or "",
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                },
            }
            for call in message.tool_calls
        ],
    }


def timed_call(fn: Callable, *args, **kwargs) -> tuple[Any, float]:
    """Run fn and report how long it took, for step traces."""
    started = time.perf_counter()
    result = fn(*args, **kwargs)
    return result, time.perf_counter() - started


def complete(
    prompt: str,
    model: str = DEFAULT_MODEL,
    temperature: float = TEMPERATURE_ANALYTICAL,
) -> str:
    """Single completion with no tools — used by every step except research."""
    response = _get_client().chat.completions.create(
        model=model,
        messages=[{"role": ROLE_USER, "content": prompt}],
        temperature=temperature,
    )
    return response.choices[0].message.content or ""


def run_tool_loop(
    prompt: str,
    model: str = DEFAULT_MODEL,
    temperature: float = TEMPERATURE_ANALYTICAL,
    max_turns: int = MAX_TOOL_TURNS,
) -> ToolLoopResult:
    """Run the model with tools until it stops asking for them.

    One turn = one model call plus the execution of every tool it requested.
    """
    messages: list[dict] = [{"role": ROLE_USER, "content": prompt}]
    recorded_calls: list[ToolCallRecord] = []

    for turn in range(1, max_turns + 1):
        response = _get_client().chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOL_SCHEMAS,
            temperature=temperature,
            # No max_turns here on purpose — see the module docstring.
        )
        message = response.choices[0].message
        requested_calls = getattr(message, "tool_calls", None)

        is_final_answer = not requested_calls
        if is_final_answer:
            return ToolLoopResult(
                content=message.content or "",
                tool_calls=recorded_calls,
                turns=turn,
            )

        messages.append(_assistant_message_from(message))

        for call in requested_calls:
            arguments, parse_error = _parse_arguments(call.function.arguments)
            if parse_error:
                result, failed = {"error": parse_error}, True
            else:
                result, failed = _execute_tool(call.function.name, arguments)

            recorded_calls.append(
                _record_of(call.function.name, arguments, result, failed)
            )
            messages.append(
                {
                    "role": ROLE_TOOL,
                    "tool_call_id": call.id,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                }
            )

    # The model kept asking for tools past the cap. Take one more completion
    # without tools so the step still produces an answer instead of nothing.
    logger.warning("Tool loop hit the %d-turn limit; forcing a final answer", max_turns)
    messages.append({"role": ROLE_USER, "content": FORCE_ANSWER_PROMPT})
    final = _get_client().chat.completions.create(
        model=model, messages=messages, temperature=temperature
    )
    return ToolLoopResult(
        content=final.choices[0].message.content or "",
        tool_calls=recorded_calls,
        turns=max_turns,
        hit_turn_limit=True,
    )
