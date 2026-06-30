"""Claude provider (default): vision-capable narration via the Anthropic API."""

from __future__ import annotations

import base64

from anthropic import AsyncAnthropic

from app.config import DIAGRAMS_DIR, settings
from app.llm.base import (
    MAX_VISION_IMAGES,
    SYSTEM_PROMPT,
    Usage,
    build_user_text,
    parse_segments,
)
from app.models import PageCapture, Segment


class ClaudeProvider:
    def __init__(self) -> None:
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Add it to .env, or switch the brain "
                "to Ollama for a fully local run."
            )
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_model
        self.last_usage = Usage()

    async def generate_segments(
        self, capture: PageCapture, use_images: bool = True
    ) -> list[Segment]:
        content: list[dict] = [{"type": "text", "text": build_user_text(capture)}]
        for d in capture.diagrams[:MAX_VISION_IMAGES] if use_images else []:
            data = (DIAGRAMS_DIR / d.png_path).read_bytes()
            content.append({"type": "text", "text": f"Diagram [{d.idx}]:"})
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": base64.b64encode(data).decode(),
                    },
                }
            )

        msg = await self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
        )
        text = "".join(b.text for b in msg.content if b.type == "text")
        u = getattr(msg, "usage", None)
        self.last_usage = Usage(
            input_tokens=int(getattr(u, "input_tokens", 0) or 0),
            output_tokens=int(getattr(u, "output_tokens", 0) or 0),
            model=getattr(msg, "model", "") or self.model,
        )
        return parse_segments(text)
