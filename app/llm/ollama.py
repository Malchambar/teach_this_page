"""Ollama provider: fully-local narration with a vision-capable model.

Nothing leaves the machine. Requires Ollama running and a vision model pulled,
e.g. `ollama pull llama3.2-vision`.
"""

from __future__ import annotations

from ollama import AsyncClient

from app.config import DIAGRAMS_DIR, settings
from app.llm.base import (
    MAX_VISION_IMAGES,
    SYSTEM_PROMPT,
    build_user_text,
    parse_segments,
)
from app.models import PageCapture, Segment


class OllamaProvider:
    def __init__(self) -> None:
        # host points at the Ollama server (local or another box on the LAN);
        # the generous timeout covers a cold model that's slow to warm up.
        self.client = AsyncClient(host=settings.ollama_host, timeout=settings.ollama_timeout)
        self.model = settings.ollama_model

    async def _supports_vision(self) -> bool:
        """Whether to attach diagram images. 'auto' asks the server about the model."""
        pref = settings.ollama_vision.lower()
        if pref in ("true", "1", "yes"):
            return True
        if pref in ("false", "0", "no"):
            return False
        try:
            info = await self.client.show(self.model)
            caps = info.get("capabilities") if isinstance(info, dict) else getattr(info, "capabilities", None)
            return "vision" in (caps or [])
        except Exception:
            return False  # unknown -> safest is captions-only (won't error a text model)

    async def generate_segments(
        self, capture: PageCapture, use_images: bool = True
    ) -> list[Segment]:
        user_msg: dict = {"role": "user", "content": build_user_text(capture)}
        if use_images and await self._supports_vision():
            user_msg["images"] = [
                str(DIAGRAMS_DIR / d.png_path)
                for d in capture.diagrams[:MAX_VISION_IMAGES]
            ]
        resp = await self.client.chat(
            model=self.model,
            format="json",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                user_msg,
            ],
        )
        return parse_segments(resp["message"]["content"])
