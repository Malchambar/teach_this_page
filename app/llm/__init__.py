"""Swappable 'brain' that turns a captured page into a narration script."""

from __future__ import annotations

from app.config import settings
from app.llm.base import LLMProvider


def get_provider(name: str | None = None) -> LLMProvider:
    """Return the configured provider; `name` overrides the env default."""
    provider = (name or settings.llm_provider or "claude").lower().replace("-", "_")
    if provider == "claude":
        from app.llm.claude import ClaudeProvider

        return ClaudeProvider()
    if provider == "claude_code":
        from app.llm.claude_code import ClaudeCodeProvider

        return ClaudeCodeProvider()
    if provider == "codex":
        from app.llm.codex import CodexProvider

        return CodexProvider()
    if provider == "ollama":
        from app.llm.ollama import OllamaProvider

        return OllamaProvider()
    raise ValueError(
        f"Unknown LLM provider: {provider!r} "
        "(use 'claude_code', 'codex', 'claude', or 'ollama')"
    )
