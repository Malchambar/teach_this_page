"""Codex provider: uses your logged-in OpenAI/ChatGPT subscription via the `codex`
CLI in headless mode (`codex exec`). No API key, no per-call billing.

Diagrams are attached directly with `-i/--image`, so the model sees them (GPT
vision). The narration JSON shape is enforced with `--output-schema`, and the
final message is captured via `-o/--output-last-message`.
"""

from __future__ import annotations

import json
import tempfile

from app.config import DIAGRAMS_DIR, ROOT, settings
from app.proc import run_capture
from app.llm.base import (
    MAX_VISION_IMAGES,
    SYSTEM_PROMPT,
    Usage,
    build_user_text,
    parse_segments,
)
from app.models import PageCapture, Segment


def _codex_default_model() -> str:
    """The model codex runs by default (from $CODEX_HOME/config.toml), since the
    --json stream doesn't report the model name and CODEX_MODEL is usually unset."""
    import os
    import tomllib
    from pathlib import Path

    cfg = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "config.toml"
    try:
        with open(cfg, "rb") as f:
            m = tomllib.load(f).get("model")
        return m if isinstance(m, str) else ""
    except Exception:
        return ""


def _codex_usage(stdout: str, model: str) -> Usage:
    """Parse token usage from codex's `--json` JSONL stream (the last event that
    carries a usage object — e.g. turn.completed). No cost: codex is subscription."""
    inp = out = 0
    for line in (stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        u = ev.get("usage")
        if isinstance(u, dict):
            inp = int(u.get("input_tokens", inp) or inp)
            out = int(u.get("output_tokens", out) or out)
    return Usage(input_tokens=inp, output_tokens=out, model=model or _codex_default_model() or "codex")

# OpenAI structured-output schema (strict: all props required, no extras).
_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "speak": {"type": "string"},
                    "image_idx": {"type": ["integer", "null"]},
                    "show": {"type": "string"},
                    "pause": {"type": "boolean"},
                },
                "required": ["speak", "image_idx", "show", "pause"],
            },
        }
    },
    "required": ["segments"],
}


class CodexProvider:
    def __init__(self) -> None:
        self.bin = settings.codex_bin
        self.model = settings.codex_model
        self.last_usage = Usage()

    async def generate_segments(
        self, capture: PageCapture, use_images: bool = True
    ) -> list[Segment]:
        diagrams = capture.diagrams[:MAX_VISION_IMAGES] if use_images else []
        head = [SYSTEM_PROMPT, ""]
        if use_images:
            manifest = "\n".join(
                f"  [{d.idx}] (attached image {i + 1})" for i, d in enumerate(diagrams)
            )
            head += ["The diagrams are attached as images, in this order:", manifest, ""]
        prompt = "\n".join([*head, build_user_text(capture), "", "Output ONLY the JSON object."])

        with tempfile.TemporaryDirectory() as td:
            out_file = f"{td}/out.txt"
            schema_file = f"{td}/schema.json"
            with open(schema_file, "w") as f:
                json.dump(_SCHEMA, f)

            args = [
                self.bin, "exec",
                "--json",  # emit JSONL events to stdout so we can read token usage
                "-s", "read-only",
                "--skip-git-repo-check",
                "-o", out_file,
                "--output-schema", schema_file,
            ]
            if self.model:
                args += ["-m", self.model]
            for d in diagrams:
                args += ["-i", str(DIAGRAMS_DIR / d.png_path)]

            try:
                _, stdout, err = await run_capture(
                    args, input_text=prompt, cwd=str(ROOT), timeout=settings.codex_timeout
                )
            except FileNotFoundError as e:
                raise RuntimeError(
                    f"Could not find the '{self.bin}' CLI. Install Codex or set CODEX_BIN."
                ) from e

            try:
                with open(out_file) as f:
                    result = f.read()
            except FileNotFoundError:
                raise RuntimeError(f"codex produced no output. stderr: {(err or '')[:400]}") from None

        if not result.strip():
            raise RuntimeError(f"codex returned empty output. stderr: {(err or '')[:400]}")
        self.last_usage = _codex_usage(stdout, self.model)
        return parse_segments(result)
