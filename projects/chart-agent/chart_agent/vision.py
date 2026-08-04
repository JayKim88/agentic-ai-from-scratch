"""Build image messages for whichever provider is being addressed.

This is the part of the project aisuite does not cover. It normalises *calls* —
one `provider:model` string picks the client — but not *message content*. Its
OpenAI path hands dicts straight through, and so does its Anthropic path, which
means an OpenAI-shaped image block reaches Anthropic unchanged and is rejected.
The two formats differ:

    OpenAI      {"type": "image_url",
                 "image_url": {"url": "data:image/png;base64,…"}}

    Anthropic   {"type": "image",
                 "source": {"type": "base64", "media_type": "image/png", "data": "…"}}

The lab reaches the same conclusion from the other direction: it keeps separate
`image_openai_call` and `image_anthropic_call` helpers. Same split, made once
here instead of at every call site.

Text-only calls stay on aisuite, where the abstraction does hold.
"""

from __future__ import annotations

import base64
from pathlib import Path

from . import config

# --- constants ---

# The workflow only ever writes PNG; JPEG is here because the lab's earlier
# version saved .jpg and `--from-chart` can be pointed at one.
MEDIA_TYPE_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


# --- helpers ---


def _media_type_of(path: Path) -> str:
    media_type = MEDIA_TYPE_BY_SUFFIX.get(path.suffix.lower())
    if media_type is None:
        supported = ", ".join(sorted(MEDIA_TYPE_BY_SUFFIX))
        raise ValueError(f"unsupported image type {path.suffix!r} for {path}. Supported: {supported}.")
    return media_type


def _openai_content(prompt: str, media_type: str, payload: str) -> list[dict]:
    return [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{payload}"}},
    ]


def _anthropic_content(prompt: str, media_type: str, payload: str) -> list[dict]:
    # Same order as the OpenAI branch on purpose. An earlier version put the
    # image first, on the recollection that Anthropic prefers it that way —
    # unverified, and it would have made the two providers differ in block
    # order as well as block shape. Comparing critiques across providers is one
    # of the experiments the lab asks for, and it only reads cleanly when the
    # format is the single variable.
    return [
        {"type": "text", "text": prompt},
        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": payload}},
    ]


# --- main export ---


def encode_image_b64(path: str | Path) -> tuple[str, str]:
    """Return `(media_type, base64_payload)` for an image on disk.

    Mirrors the lab's `utils.encode_image_b64`.

    Raises:
        FileNotFoundError: no such image.
        ValueError: the suffix is not a format the providers accept.
    """
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"{source} does not exist — nothing to send to the model.")

    media_type = _media_type_of(source)
    payload = base64.b64encode(source.read_bytes()).decode("ascii")
    return media_type, payload


def build_image_message(model: str, prompt: str, image_path: str | Path) -> dict:
    """Build the single user message carrying `prompt` and the chart image.

    The shape depends on the provider behind `model`; see the module docstring
    for why that cannot be left to aisuite.
    """
    media_type, payload = encode_image_b64(image_path)

    content = (
        _anthropic_content(prompt, media_type, payload)
        if config.is_anthropic(model)
        else _openai_content(prompt, media_type, payload)
    )
    return {"role": "user", "content": content}


def describe_message(message: dict) -> str:
    """Summarise an image message for logs, without dumping the base64 blob.

    Completion criterion 3 asks for proof that an image really was sent. A
    critique that happens to differ is not proof — the models are not
    deterministic — so the request itself has to be inspectable.
    """
    parts = []
    for block in message.get("content", []):
        kind = block.get("type")
        if kind == "text":
            parts.append(f"text({len(block['text'])} chars)")
        elif kind == "image_url":
            url = block["image_url"]["url"]
            header, _, data = url.partition(",")
            parts.append(f"image_url[{header}] ({len(data)} b64 chars)")
        elif kind == "image":
            source = block["source"]
            parts.append(f"image[{source['media_type']}] ({len(source['data'])} b64 chars)")
        else:
            parts.append(f"{kind}?")

    return " + ".join(parts)
