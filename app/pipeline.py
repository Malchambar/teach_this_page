"""Orchestrates a narrate request: capture -> script -> audio -> Lesson."""

from __future__ import annotations

from app import tts
from app.capture import capture_active_tab
from app.config import DIAGRAMS_DIR
from app.llm import get_provider
from app.models import Lesson


def _clear_diagrams() -> None:
    for f in DIAGRAMS_DIR.glob("*.png"):
        f.unlink(missing_ok=True)


async def build_lesson(
    voice: str | None = None,
    speed: float | None = None,
    provider: str | None = None,
) -> Lesson:
    """Read the active Chrome tab and return a fully narrated, audio-backed lesson."""
    _clear_diagrams()

    capture = await capture_active_tab()
    if not capture.text and not capture.diagrams:
        raise ValueError("Nothing to narrate: no readable text or diagrams on this page.")

    brain = get_provider(provider)
    segments = await brain.generate_segments(capture)

    # Synthesize sequentially — pages are short and it keeps Kokoro memory steady.
    for seg in segments:
        seg.audio_path = await tts.synthesize(seg.speak, voice=voice, speed=speed)

    return Lesson(
        url=capture.url,
        title=capture.title,
        segments=segments,
        diagrams=capture.diagrams,
    )
