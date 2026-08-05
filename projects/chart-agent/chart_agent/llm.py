"""Model calls, text and image, through aisuite.

The lab has two entry points: `utils.get_response(model, prompt)` for text and a
pair of `image_*_call` helpers for vision. The split here is the same, except
the provider branch lives in `vision.py` — by the time a message reaches this
module it is already shaped for its destination, so both paths can share one
client.
"""

from __future__ import annotations

import aisuite

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

    response = _get_client().chat.completions.create(
        model=model,
        messages=[message],
        **_token_limit_kwargs(model),
    )
    return _content_of(response), summary
