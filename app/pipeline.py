"""Orchestrates a narrate request: capture -> script -> audio -> Lesson."""

from __future__ import annotations

from app import tts
from app.capture import capture_active_tab
from app.config import DIAGRAMS_DIR, settings
from app.llm import get_provider
from app.llm.vision import describe_diagrams
from app.models import Lesson

_OFF = {"off", "none", ""}

# The most recently captured page, kept as reference context for the chat panel.
_last_context: dict | None = None

# Full detail of the last build (page text actually used, diagrams, and the
# segment script), exposed at /api/debug for troubleshooting. In-memory only —
# never written to disk, so it's gone when the app exits (no-retention posture).
_last_debug: dict | None = None

# Coarse build progress, polled by the UI so it can narrate what's happening
# ("Reading the page…", "Writing the lesson…") instead of a silent wait.
_progress: dict = {"stage": "idle", "label": ""}


def get_progress() -> dict:
    return dict(_progress)


def _set_progress(stage: str, label: str) -> None:
    _progress["stage"] = stage
    _progress["label"] = label


def last_context() -> dict | None:
    return _last_context


def get_debug() -> dict | None:
    return _last_debug


def _clear_diagrams() -> None:
    for f in DIAGRAMS_DIR.glob("*.png"):
        f.unlink(missing_ok=True)


def _norm(name: str) -> str:
    return name.lower().replace("-", "_")


async def build_lesson(
    vision: str | None = None, writer: str | None = None, step_mode: str = "auto"
) -> Lesson:
    """Read the active Chrome tab and return the narration script (no audio yet).

    Engine roles (see config): a `vision` engine describes the diagrams and a
    `writer` engine narrates. Three cases:
      - vision == "off": writer narrates from Cisco's alt-text captions only.
      - vision == writer: one combined pass (the engine sees the images itself).
      - otherwise: split — describe with `vision`, then write from descriptions.

    Audio is rendered lazily per segment by `synth_segment`, so playback starts
    fast; playback speed is live in the player, so audio is rendered neutral.
    """
    _clear_diagrams()
    _set_progress("reading", "Reading the page…")

    # capture_active_tab raises a diagnostic ValueError if the page yields nothing.
    try:
        capture = await capture_active_tab(on_stage=_set_progress, step_mode=step_mode)
    except Exception:
        _set_progress("idle", "")
        raise

    vision = vision or settings.vision_provider
    writer = writer or settings.writer_provider or settings.llm_provider
    brain = get_provider(writer)

    if capture.steps:
        # Step Mode: the page captured as an ordered procedure. The writer makes
        # one segment per step from the step text (no images attached, no vision
        # pass — step photos carry no info the text doesn't); the app maps each
        # segment to its step's image group + anchor below.
        _set_progress("writing", f"Writing the lesson — {len(capture.steps)} steps…")
        segments = await brain.generate_segments(capture, use_images=False)
    elif _norm(vision) in _OFF:
        _set_progress("writing", "Writing the lesson…")
        segments = await brain.generate_segments(capture, use_images=False)
    elif _norm(vision) == _norm(writer):
        _set_progress("writing", "Reading the diagrams and writing the lesson…")
        segments = await brain.generate_segments(capture, use_images=True)
    else:
        _set_progress("vision", f"Looking at {len(capture.diagrams)} diagram(s)…")
        await describe_diagrams(vision, capture.diagrams)
        _set_progress("writing", "Writing the lesson…")
        segments = await brain.generate_segments(capture, use_images=False)

    # Step Mode: attach each segment's step image group + page anchor authoritatively
    # from the captured steps. Prefer the model's step_idx, but fall back to segment
    # ORDER when it produced one segment per step (the prompt requires in-order, and
    # models are unreliable about echoing step_idx — null/str/1-based), so images
    # attach regardless.
    if capture.steps:
        n = len(capture.steps)
        one_to_one = len(segments) == n
        for i, s in enumerate(segments):
            si = s.step_idx
            if not isinstance(si, int) or not (0 <= si < n):
                si = i if one_to_one else None
            if si is None:
                continue
            st = capture.steps[si]
            s.step_idx = si
            s.image_idxs = list(st.image_idxs)
            s.image_idx = st.image_idxs[0] if st.image_idxs else None
            s.source_anchor = st.anchor or None

    _set_progress("done", "")

    global _last_context, _last_debug
    _last_context = {
        "title": capture.title,
        "url": capture.url,
        "text": capture.text,
        "diagrams": [
            {"idx": d.idx, "desc": d.description or d.alt or d.context or ""}
            for d in capture.diagrams
        ],
    }
    _last_debug = {
        "url": capture.url,
        "title": capture.title,
        "engines": {"vision": vision, "writer": writer},
        "text_chars": len(capture.text or ""),
        "text": capture.text,
        "diagram_count": len(capture.diagrams),
        "diagrams": [
            {
                "idx": d.idx,
                "file": d.png_path.rsplit("/", 1)[-1],
                "alt": d.alt,
                "context": d.context,
                "description": d.description,
            }
            for d in capture.diagrams
        ],
        "step_count": len(capture.steps),
        "steps": [
            {
                "number": st.number,
                "title": st.title,
                "anchor": st.anchor,
                "image_idxs": st.image_idxs,
                "text_chars": len(st.text or ""),
            }
            for st in capture.steps
        ],
        "segment_count": len(segments),
        "segments": [
            {
                "idx": s.idx,
                "step_idx": s.step_idx,
                "image_idx": s.image_idx,
                "image_idxs": s.image_idxs,
                "source_anchor": s.source_anchor,
                "pause": s.pause,
                "show": s.show,
                "speak": s.speak,
            }
            for s in segments
        ],
    }

    return Lesson(
        url=capture.url,
        title=capture.title,
        segments=segments,
        diagrams=capture.diagrams,
        steps=capture.steps,
    )


async def synth_segment(lesson: Lesson, idx: int, voice: str) -> str:
    """Render one segment's audio in `voice` and return its filename (disk-cached)."""
    seg = lesson.segments[idx]
    return await tts.synthesize(seg.speak, voice=voice)
