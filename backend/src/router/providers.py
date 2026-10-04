"""Picks the small-model backend from SMALL_LLM_PROVIDER."""

from __future__ import annotations

from ..config import Settings, get_settings
from .small_llm import GeminiLLM

# from .local_llm import LocalLLM  # DISABLED: uncomment with local_llm.py


def get_small_llm(settings: Settings | None = None):
    s = settings or get_settings()
    if s.small_llm_provider == "gemini":
        return GeminiLLM(s)
    # if s.small_llm_provider == "local":
    #     return LocalLLM(s)
    raise ValueError(f"Unsupported SMALL_LLM_PROVIDER: {s.small_llm_provider!r}")