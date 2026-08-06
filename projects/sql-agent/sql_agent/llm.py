"""Text completions through aisuite.

The lab calls `client.chat.completions.create(...)` inline in each of its three
functions. Same call here, in one place, with `temperature` as an argument
rather than a literal — the review conditions differ by temperature, so it has
to be something a caller sets.
"""

from __future__ import annotations

import aisuite

from sql_agent import config

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
    by sending it. A provider requirement rather than a caller's knob, which is
    why it is not a parameter.
    """
    return {"max_tokens": config.MAX_RESPONSE_TOKENS} if config.is_anthropic(model) else {}


def _content_of(response) -> str:
    """Pull the assistant text out of an aisuite response.

    Raises:
        RuntimeError: the model returned nothing. Every caller here expects SQL
            or a review, so empty output is a real failure rather than an empty
            string to pass along.
    """
    content = response.choices[0].message.content
    if not (content or "").strip():
        raise RuntimeError("model returned an empty response")
    return content


# --- main export ---


def complete(model: str, prompt: str, temperature: float) -> str:
    """Send a text prompt and return the reply.

    `temperature` is required rather than defaulted: which value applies is the
    difference between two of the review conditions, so leaving it implicit
    would make the comparison depend on a default nobody looked at.
    """
    config.require_key(model)

    response = _get_client().chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        **_token_limit_kwargs(model),
    )
    return _content_of(response)
