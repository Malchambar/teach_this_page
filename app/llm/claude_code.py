"""Claude Code provider: uses your logged-in Claude subscription via the `claude`
CLI in headless mode. No API key, no per-call billing — it draws on your plan.

It reads each captured diagram with the CLI's read-only Read tool, so it actually
sees the images (strong vision) before writing the narration.
"""

from __future__ import annotations

import json

from app.config import ROOT, settings
from app.proc import run_capture
from app.llm.base import (
    MAX_VISION_IMAGES,
    SYSTEM_PROMPT,
    Usage,
    build_user_text,
    parse_segments,
    usage_from_claude_envelope,
)
from app.models import PageCapture, Segment


class ClaudeCodeProvider:
    def __init__(self) -> None:
        self.bin = settings.claude_bin
        self.model = settings.claude_code_model
        self.last_usage = Usage()

    def _build_prompt(self, capture: PageCapture, use_images: bool) -> str:
        parts = [SYSTEM_PROMPT, ""]
        if use_images:
            diagrams = capture.diagrams[:MAX_VISION_IMAGES]
            parts += [
                "Use the Read tool to open each diagram image file below so you can "
                "describe it accurately, then write the narration.",
                "DIAGRAM IMAGE FILES (number -> path, relative to the working directory):",
                *[f"  [{d.idx}] data/diagrams/{d.png_path}" for d in diagrams],
                "",
            ]
        parts += [
            build_user_text(capture),
            "",
            "Output ONLY the JSON object — no prose, no code fences.",
        ]
        return "\n".join(parts)

    async def generate_segments(
        self, capture: PageCapture, use_images: bool = True
    ) -> list[Segment]:
        prompt = self._build_prompt(capture, use_images)
        tools = "Read" if use_images else ""
        args = [self.bin, "-p", "--output-format", "json"]
        if tools:
            args += ["--allowedTools", tools]
        if self.model:
            args += ["--model", self.model]

        try:
            rc, out, err = await run_capture(
                args, input_text=prompt, cwd=str(ROOT), timeout=settings.claude_code_timeout
            )
        except FileNotFoundError as e:
            raise RuntimeError(
                f"Could not find the '{self.bin}' CLI. Install Claude Code or set "
                "CLAUDE_BIN to its full path."
            ) from e

        if rc != 0:
            raise RuntimeError(f"claude CLI failed: {(err or out)[:400]}")

        try:
            env = json.loads(out)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Unexpected claude output: {out[:400]}") from e

        if env.get("is_error"):
            raise RuntimeError(f"claude returned an error: {str(env.get('result'))[:400]}")
        self.last_usage = usage_from_claude_envelope(env)
        if not self.last_usage.model:
            self.last_usage.model = self.model or "claude_code"
        return parse_segments(env.get("result", ""))
