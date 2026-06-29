"""Provider interface + shared helpers for building/parsing the narration."""

from __future__ import annotations

import json
from typing import Protocol

from app.models import PageCapture, Segment

# Cap how many diagrams we send as vision input, to keep payloads sane.
MAX_VISION_IMAGES = 12
# Cap page text so we don't blow the context window on huge pages.
MAX_TEXT_CHARS = 16000


class LLMProvider(Protocol):
    async def generate_segments(self, capture: PageCapture) -> list[Segment]: ...


SYSTEM_PROMPT = """You are an engaging, plain-spoken instructor helping a network \
engineer learn from a training page. Turn the page into a spoken walkthrough that \
holds attention — teach the concept, don't read it out word for word.

Rules:
- Break the explanation into short segments, each 2-5 sentences of natural speech.
- When a diagram helps, set image_idx to that diagram's number and actively talk the \
listener through it: name what to look at, trace the flow, point out the key parts.
- Order segments so diagrams appear right as you discuss them.
- This text is READ ALOUD. No markdown, no code fences, no URLs, no bullet symbols, \
no citations. Spell out acronyms the first time if useful.
- Be accurate to the page. Don't invent facts or specs.

Return ONLY JSON of this exact shape:
{"segments": [{"speak": "<spoken text>", "image_idx": <diagram number or null>}]}"""


def build_user_text(capture: PageCapture) -> str:
    """The text half of the prompt: page text + a diagram manifest by index."""
    lines = [f"PAGE TITLE: {capture.title}", f"URL: {capture.url}", "", "PAGE TEXT:"]
    lines.append(capture.text[:MAX_TEXT_CHARS] or "(no extractable text)")
    if capture.diagrams:
        lines += ["", "DIAGRAMS (refer to these by number in image_idx):"]
        for d in capture.diagrams[:MAX_VISION_IMAGES]:
            desc = d.alt or d.context or "(no caption)"
            lines.append(f"  [{d.idx}] {desc}")
    return "\n".join(lines)


def parse_segments(raw: str) -> list[Segment]:
    """Pull the JSON out of a model response and build Segments, tolerantly.

    Handles the intended shape ({"segments":[{"speak","image_idx"}]}) as well as
    common drift: a bare array, segments as plain strings, or "text" for "speak".
    """
    text = raw.strip()
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    ends = [i for i in (text.rfind("}"), text.rfind("]")) if i != -1]
    if not starts or not ends:
        raise ValueError(f"Model did not return JSON. Got: {raw[:200]}")
    data = json.loads(text[min(starts) : max(ends) + 1])

    if isinstance(data, dict):
        items = data.get("segments") or data.get("Segments") or []
    elif isinstance(data, list):
        items = data
    else:
        items = []

    segments: list[Segment] = []
    for item in items:
        if isinstance(item, str):
            speak, image_idx = item.strip(), None
        elif isinstance(item, dict):
            speak = (item.get("speak") or item.get("text") or "").strip()
            image_idx = item.get("image_idx")
            if not isinstance(image_idx, int):
                image_idx = None
        else:
            continue
        if not speak:
            continue
        segments.append(Segment(idx=len(segments), speak=speak, image_idx=image_idx))
    if not segments:
        raise ValueError(f"Model returned no usable segments. Got: {raw[:200]}")
    return segments
