"""Generic provider for any OpenAI-compatible API: Gemini, Grok (xAI), OpenRouter.

All three speak the OpenAI chat-completions protocol, so one client handles them —
only the base URL, API key, and model differ. Each needs its key in .env. Vision
works by inlining diagrams as base64 data-URL image parts.
"""

from __future__ import annotations

import base64

from openai import AsyncOpenAI

from app.config import DIAGRAMS_DIR, settings
from app.llm.base import (
    MAX_VISION_IMAGES,
    SYSTEM_PROMPT,
    Usage,
    build_user_text,
    parse_segments,
)
from app.models import PageCapture, Segment


def resolve(name: str) -> tuple[str, str, str, str]:
    """Return (base_url, api_key, model, env_var_name) for a provider key."""
    n = name.lower()
    if n == "gemini":
        return (
            "https://generativelanguage.googleapis.com/v1beta/openai/",
            settings.gemini_api_key,
            settings.gemini_model,
            "GEMINI_API_KEY",
        )
    if n == "grok":
        return ("https://api.x.ai/v1", settings.xai_api_key, settings.grok_model, "XAI_API_KEY")
    if n == "openrouter":
        return (
            "https://openrouter.ai/api/v1",
            settings.openrouter_api_key,
            settings.openrouter_model,
            "OPENROUTER_API_KEY",
        )
    raise ValueError(f"Unknown OpenAI-compatible provider: {name!r}")


def image_part(png_path) -> dict:
    data = base64.b64encode(png_path.read_bytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{data}"}}


class OpenAICompatProvider:
    def __init__(self, name: str) -> None:
        self.name = name
        base_url, key, model, env = resolve(name)
        if not key:
            raise RuntimeError(f"{env} is not set. Add it to .env to use {name}.")
        if not model:
            raise RuntimeError(
                f"No model set for {name}. Set its model in .env "
                "(e.g. OPENROUTER_MODEL=google/gemini-2.5-flash)."
            )
        self.client = AsyncOpenAI(base_url=base_url, api_key=key)
        self.model = model
        self.last_usage = Usage()

    async def generate_segments(
        self, capture: PageCapture, use_images: bool = True
    ) -> list[Segment]:
        content: list[dict] = [{"type": "text", "text": build_user_text(capture)}]
        if use_images:
            for d in capture.diagrams[:MAX_VISION_IMAGES]:
                content.append({"type": "text", "text": f"Diagram [{d.idx}]:"})
                content.append(image_part(DIAGRAMS_DIR / d.png_path))

        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            max_tokens=8192,
        )
        u = getattr(resp, "usage", None)
        self.last_usage = Usage(
            input_tokens=int(getattr(u, "prompt_tokens", 0) or 0),
            output_tokens=int(getattr(u, "completion_tokens", 0) or 0),
            model=getattr(resp, "model", "") or self.model,
        )
        return parse_segments(resp.choices[0].message.content or "")
