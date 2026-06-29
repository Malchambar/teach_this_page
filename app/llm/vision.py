"""Diagram describer for split mode: a vision engine turns each diagram into a
short text description, which the writer engine then narrates from.

Descriptions are cached on disk by image content + engine, so re-running or
re-voicing the same page skips the vision work entirely. Describes run
concurrently (bounded) to keep the vision pass quick.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import subprocess
import sys
import tempfile

from app.config import DESCRIPTIONS_DIR, DIAGRAMS_DIR, ROOT, settings
from app.models import Diagram

DESCRIBE_PROMPT = (
    "Describe this diagram for a narrator who will explain it aloud to a student. "
    "In 2-4 sentences, say what it shows, the overall flow or structure, and the key "
    "labeled parts or callouts. Plain prose only — no markdown, no preamble."
)

_OFF = {"off", "none", ""}


def _cache_file(png: bytes, provider: str):
    key = hashlib.sha1(png + provider.encode()).hexdigest()[:16]
    return DESCRIPTIONS_DIR / f"{key}.txt"


async def describe_diagrams(provider: str, diagrams: list[Diagram], concurrency: int = 3) -> None:
    """Fill each diagram's `.description` using the vision engine (cached, concurrent)."""
    if provider.lower() in _OFF or not diagrams:
        return
    sem = asyncio.Semaphore(concurrency)

    async def one(d: Diagram) -> None:
        async with sem:
            try:
                d.description = await _describe_cached(provider, d)
            except Exception as e:  # fall back to alt-text for this one
                print(f"[vision] describe failed for diagram {d.idx}: {e}", file=sys.stderr)

    await asyncio.gather(*(one(d) for d in diagrams))


async def _describe_cached(provider: str, d: Diagram) -> str:
    path = DIAGRAMS_DIR / d.png_path
    png = path.read_bytes()
    cache = _cache_file(png, provider)
    if cache.exists():
        return cache.read_text().strip()
    desc = (await _describe(provider, path)).strip()
    if desc:
        cache.write_text(desc)
    return desc


async def _describe(provider: str, path) -> str:
    p = provider.lower().replace("-", "_")
    if p == "claude_code":
        return await _describe_claude_code(path)
    if p == "codex":
        return await _describe_codex(path)
    if p == "ollama":
        return await _describe_ollama(path)
    if p == "claude":
        return await _describe_claude_api(path)
    if p in ("gemini", "grok", "openrouter"):
        return await _describe_openai_compat(p, path)
    raise ValueError(f"Unknown vision provider: {provider!r}")


async def _describe_openai_compat(name: str, path) -> str:
    from app.llm.openai_compat import OpenAICompatProvider, image_part

    prov = OpenAICompatProvider(name)
    resp = await prov.client.chat.completions.create(
        model=prov.model,
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": [{"type": "text", "text": DESCRIBE_PROMPT}, image_part(path)],
        }],
    )
    return resp.choices[0].message.content or ""


async def _describe_claude_code(path) -> str:
    prompt = f"Read the image file data/diagrams/{path.name} and {DESCRIBE_PROMPT}"
    args = [settings.claude_bin, "-p", "--output-format", "json", "--allowedTools", "Read"]
    if settings.claude_code_model:
        args += ["--model", settings.claude_code_model]

    def run():
        return subprocess.run(
            args, input=prompt, capture_output=True, text=True,
            cwd=str(ROOT), timeout=settings.claude_code_timeout,
        )

    proc = await asyncio.to_thread(run)
    env = json.loads(proc.stdout)
    if env.get("is_error"):
        raise RuntimeError(str(env.get("result"))[:200])
    return env.get("result", "")


async def _describe_codex(path) -> str:
    with tempfile.TemporaryDirectory() as td:
        out = f"{td}/out.txt"
        args = [
            settings.codex_bin, "exec", "-s", "read-only",
            "--skip-git-repo-check", "-o", out, "-i", str(path),
        ]
        if settings.codex_model:
            args += ["-m", settings.codex_model]

        def run():
            return subprocess.run(
                args, input=DESCRIBE_PROMPT, capture_output=True, text=True,
                cwd=str(ROOT), timeout=settings.codex_timeout,
            )

        proc = await asyncio.to_thread(run)
        try:
            with open(out) as f:
                return f.read()
        except FileNotFoundError:
            raise RuntimeError((proc.stderr or "")[:200]) from None


async def _describe_ollama(path) -> str:
    from ollama import AsyncClient

    client = AsyncClient(host=settings.ollama_host, timeout=settings.ollama_timeout)
    resp = await client.chat(
        model=settings.ollama_model,
        messages=[{"role": "user", "content": DESCRIBE_PROMPT, "images": [str(path)]}],
    )
    return resp["message"]["content"]


async def _describe_claude_api(path) -> str:
    from anthropic import AsyncAnthropic

    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    data = base64.b64encode(path.read_bytes()).decode()
    msg = await client.messages.create(
        model=settings.claude_model,
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": DESCRIBE_PROMPT},
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": data}},
            ],
        }],
    )
    return "".join(b.text for b in msg.content if b.type == "text")
