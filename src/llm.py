"""
Model provider abstraction. One function: images + prompt + JSON schema in, dict out.

Providers (auto-detected from the environment, first match wins):
  claude  - ANTHROPIC_API_KEY set. Uses the official SDK with structured outputs, so the
            response is guaranteed to match the schema. Default model claude-opus-5-5.
            Server-side refusal fallback is enabled by default (betas server-side-fallback-2026-07-01).
  gemini  - GEMINI_API_KEY set. Free tier via REST (same pattern as the Investor Intelligence
            Engine's RUN-LLM.bat). Default model gemini-2.5-flash. JSON mode, validated locally.

Override with LABEL_DECODER_PROVIDER=claude|gemini and LABEL_DECODER_MODEL=<model id>.
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import time

import requests
from PIL import Image

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = {"claude": "claude-opus-5-5", "gemini": "gemini-2.5-flash"}
MAX_SIDE = 1568   # long edge in px; above this vision tokens rise with no OCR gain


def provider() -> str | None:
    forced = os.environ.get("LABEL_DECODER_PROVIDER")
    if forced:
        return forced
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "claude"
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    return None


def model_id(prov: str) -> str:
    return os.environ.get("LABEL_DECODER_MODEL") or DEFAULT_MODEL[prov]


def _prep_image(img: bytes | str | Image.Image) -> tuple[str, str]:
    """Return (base64, media_type) with the image downscaled to MAX_SIDE and re-encoded as JPEG."""
    if isinstance(img, (bytes, bytearray)):
        im = Image.open(io.BytesIO(img))
    elif isinstance(img, str):
        im = Image.open(img)
    else:
        im = img
    im = im.convert("RGB")
    w, h = im.size
    scale = MAX_SIDE / max(w, h)
    if scale < 1:
        im = im.resize((int(w * scale), int(h * scale)))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=88)
    return base64.standard_b64encode(buf.getvalue()).decode("ascii"), "image/jpeg"


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not m:
            raise
        return json.loads(m.group(0))


def vision_json(images: list, prompt: str, schema: dict, system: str = "", max_tokens: int = 8000) -> dict:
    """Send images + prompt, get a dict that matches `schema`. Raises RuntimeError when no provider."""
    prov = provider()
    if prov is None:
        raise RuntimeError("No model key found. Set ANTHROPIC_API_KEY (Claude) or GEMINI_API_KEY (free).")
    if prov == "claude":
        return _claude(images, prompt, schema, system, max_tokens)
    return _gemini(images, prompt, schema, system, max_tokens)


def text_json(prompt: str, schema: dict, system: str = "", max_tokens: int = 8000) -> dict:
    return vision_json([], prompt, schema, system, max_tokens)


# ---------------------------------------------------------------------------- Claude
def _claude(images, prompt, schema, system, max_tokens) -> dict:
    import anthropic

    client = anthropic.Anthropic()
    content = []
    for img in images:
        b64, mt = _prep_image(img)
        content.append({"type": "image", "source": {"type": "base64", "media_type": mt, "data": b64}})
    content.append({"type": "text", "text": prompt})
    kwargs = dict(
        model=model_id("claude"),
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": content}],
        output_config={"format": {"type": "json_schema", "schema": schema}, "effort": "medium"},
    )
    if system:
        kwargs["system"] = system
    try:
        resp = client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
    except (TypeError, anthropic.BadRequestError):
        resp = client.messages.create(**kwargs)
    if resp.stop_reason == "refusal":
        cat = getattr(getattr(resp, "stop_details", None), "category", None)
        raise RuntimeError(f"Model declined the request (category={cat}).")
    text = next(b.text for b in resp.content if b.type == "text")
    return _extract_json(text)


# ---------------------------------------------------------------------------- Gemini
def _gemini(images, prompt, schema, system, max_tokens) -> dict:
    parts = []
    for img in images:
        b64, mt = _prep_image(img)
        parts.append({"inline_data": {"mime_type": mt, "data": b64}})
    parts.append({"text": prompt})
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {"response_mime_type": "application/json", "maxOutputTokens": max_tokens,
                             "temperature": 0.1},
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    headers = {"x-goog-api-key": os.environ["GEMINI_API_KEY"], "Content-Type": "application/json"}
    url = GEMINI_URL.format(model=model_id("gemini"))
    for attempt in range(5):
        r = requests.post(url, json=body, headers=headers, timeout=120)
        if r.status_code == 429 or r.status_code >= 500:
            wait = 2 ** attempt * 3
            print(f"  gemini {r.status_code}, retry in {wait}s")
            time.sleep(wait)
            continue
        r.raise_for_status()
        data = r.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            raise RuntimeError(f"Gemini returned no text: {json.dumps(data)[:400]}")
        return _extract_json(text)
    raise RuntimeError("Gemini: gave up after 5 retries (rate limit).")
