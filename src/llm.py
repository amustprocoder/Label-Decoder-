"""
Model provider abstraction. One function: images + prompt + JSON schema in, dict out.

Providers (auto-detected from the environment, first match wins):
  claude  - ANTHROPIC_API_KEY set. Uses the official SDK with structured outputs, so the
            response is guaranteed to match the schema. Default model claude-opus-5-5.
            Server-side refusal fallback is enabled by default (betas server-side-fallback-2026-07-01).
  gemini  - GEMINI_API_KEY set. Free tier via REST (same pattern as the Investor Intelligence
            Engine's RUN-LLM.bat). Default model gemini-3.8-flash, then the GEMINI_FALLBACKS list. JSON mode, validated locally.

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
DEFAULT_MODEL = {"claude": "claude-opus-5-5", "gemini": "gemini-3.8-flash"}
# Google retires dated models and the newest one is often "busy" on the free tier, so one model is not enough.
# Tried in order after the default; the last is an alias that always points at a live model.
GEMINI_FALLBACKS = ["gemini-3.5-flash", "gemini-flash-lite-latest"]
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
    if schema:
        # Claude gets the schema through structured outputs; Gemini's JSON mode only promises "some JSON", so the
        # field names have to be spelled out or it invents its own and the rules layer finds nothing.
        prompt += ("\n\nReturn ONE JSON object that follows this JSON Schema exactly: the same key names, every "
                   "required key present, null where the pack does not print a value.\n" + json.dumps(schema))
    parts.append({"text": prompt})
    body = {
        "contents": [{"parts": parts}],
        # no temperature: the Gemini 3 models are tuned for their default, and a low one is not what keeps the
        # answer on the label (the schema and the "printed numbers only" instruction do that)
        "generationConfig": {"response_mime_type": "application/json", "maxOutputTokens": max_tokens},
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    # a key saved with a stray space or quote (easy to do with setx) should still work
    headers = {"x-goog-api-key": os.environ["GEMINI_API_KEY"].strip().strip('"\''), "Content-Type": "application/json"}
    # an explicit LABEL_DECODER_MODEL means "this model only"; otherwise walk the fallback list
    models = [model_id("gemini")] + ([] if os.environ.get("LABEL_DECODER_MODEL") else GEMINI_FALLBACKS)
    last = "no model answered"
    for model in models:
        url = GEMINI_URL.format(model=model)
        for attempt in range(2):
            try:
                r = requests.post(url, json=body, headers=headers, timeout=75)
            except requests.Timeout:
                last = f"{model}: timed out"
                break                                   # a hung model will not get faster: next one
            if r.status_code == 404:
                last = f"{model}: retired"
                break
            if r.status_code == 429 or r.status_code >= 500:
                last = f"{model}: HTTP {r.status_code} (busy or rate limited)"
                print(f"  gemini {model} {r.status_code}, retry in 4s")
                time.sleep(4)
                continue
            r.raise_for_status()
            data = r.json()
            try:
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return _extract_json(text)
            except (KeyError, IndexError, json.JSONDecodeError):
                # no usable answer: the model blocked itself (finishReason RECITATION / SAFETY when asked to copy a
                # label word for word) or wrote broken JSON. Another model usually just answers.
                cand = (data.get("candidates") or [{}])[0]
                last = f"{model}: no usable answer ({cand.get('finishReason', 'unknown')})"
                print(f"  gemini {last}")
                break
    raise RuntimeError(f"Gemini: none of {', '.join(models)} answered ({last}). Try again in a minute.")
