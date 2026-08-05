"""Model calls, text and image, through aisuite.

The lab has two entry points: `utils.get_response(model, prompt)` for text and a
pair of `image_*_call` helpers for vision. The split here is the same, except
the provider branch lives in `vision.py` — by the time a message reaches this
module it is already shaped for its destination, so both paths can share one
client.
"""

from __future__ import annotations

import aisuite
import anthropic

from . import config, vision

# --- module state ---

_client: aisuite.Client | None = None


# --- helpers ---


def _get_client() -> aisuite.Client:
    """One client for the process. Providers are constructed lazily by aisuite."""
    global _client
    if _client is None:
        config.load_environment()
        _client = aisuite.Client()
    return _client


def _token_limit_kwargs(model: str) -> dict:
    """The token ceiling, for the provider that insists on one.

    Anthropic rejects a request without `max_tokens`; OpenAI treats it as
    optional and renamed it between model families, so there is nothing to gain
    by sending it. This is a provider requirement rather than a caller's knob,
    which is why it is not a parameter — a `max_tokens` argument would be
    honoured for one provider and quietly dropped for the other.
    """
    return {"max_tokens": config.MAX_RESPONSE_TOKENS} if config.is_anthropic(model) else {}


def _content_of(response) -> str:
    """Pull the assistant text out of an aisuite response.

    Raises:
        RuntimeError: the model returned no content. Empty output is a real
            failure here — every caller expects code or a critique — so it is
            not passed on as an empty string.
    """
    content = response.choices[0].message.content
    if not (content or "").strip():
        raise RuntimeError("model returned an empty response")
    return content


def _joined_text(blocks) -> str:
    """Concatenate every text block Anthropic returned.

    aisuite reads `response.content[0].text` and stops, so a reply split across
    blocks loses everything after the first, and a reply whose first block is
    not text raises on the attribute. The lab's `image_anthropic_call` collects
    them all; this is the one place its version was doing something ours was
    not.
    """
    parts = [block.text for block in (blocks or []) if getattr(block, "type", None) == "text"]
    return "".join(parts).strip()


def _anthropic_image_call(model: str, message: dict) -> str:
    """Call Anthropic directly so no text block is dropped.

    aisuite carries the request fine — its converter passes `content` through —
    but its response conversion keeps only the first block. Going through the
    SDK here is not a rejection of the abstraction; it is the one response shape
    the abstraction flattens.
    """
    config.load_environment()
    client = anthropic.Anthropic()
    reply = client.messages.create(
        model=model.split(config.PROVIDER_SEPARATOR, 1)[-1],
        max_tokens=config.MAX_RESPONSE_TOKENS,
        messages=[message],
    )

    text = _joined_text(reply.content)
    if not text:
        raise RuntimeError("model returned no text blocks")
    return text


# --- main export ---


def complete(model: str, prompt: str) -> str:
    """Send a text-only prompt. Mirrors the lab's `utils.get_response`."""
    config.require_key(model)

    response = _get_client().chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        **_token_limit_kwargs(model),
    )
    return _content_of(response)


def complete_with_image(
    model: str, prompt: str, image_path: str, log_request: bool = False
) -> tuple[str, str]:
    """Send a prompt together with an image. Returns `(content, request_summary)`.

    The summary describes the message that actually went out. Completion
    criterion 3 asks for evidence that an image was really sent, and a critique
    that happens to mention the chart is not evidence — the models are not
    deterministic. Returning it rather than only printing it means the evidence
    survives into the run's trace instead of scrolling away.
    """
    config.require_key(model)
    message = vision.build_image_message(model, prompt, image_path)
    summary = vision.describe_message(message)

    if log_request:
        print(f"[vision] {model} ← {summary}")

    if config.is_anthropic(model):
        return _anthropic_image_call(model, message), summary

    response = _get_client().chat.completions.create(
        model=model,
        messages=[message],
        **_token_limit_kwargs(model),
    )
    return _content_of(response), summary
