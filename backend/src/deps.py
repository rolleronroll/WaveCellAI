from __future__ import annotations

from functools import lru_cache

from .config import get_settings
from .pipeline import Pipeline
from .rag.sqlite_store import KnowledgeStore
from .router import ClaudeClient, Router, get_small_llm
from .translation import Translator
from .router.model_fallback import ModelFallbackLLM
from .geo import BoundaryRegistry
from pathlib import Path



@lru_cache
def get_boundaries() -> BoundaryRegistry:
    return BoundaryRegistry(Path(get_settings().data_dir) / "gis")

@lru_cache
def get_store() -> KnowledgeStore:
    return KnowledgeStore(get_settings().sqlite_file)


@lru_cache
def get_router() -> Router:
    s = get_settings()
    backup = s.model_copy(update={"gemini_model": s.gemini_fallback_model})
    small = ModelFallbackLLM(get_small_llm(s), get_small_llm(backup))
    return Router(small, ClaudeClient(s), s)


# @lru_cache
# def get_router() -> Router:
#     s = get_settings()
#     return Router(get_small_llm(s), ClaudeClient(s), s)


@lru_cache
def get_pipeline() -> Pipeline:
    router = get_router()
    # return Pipeline(get_store(), router, Translator(...), get_boundaries())
    # return Pipeline(get_store(), router, Translator(router.small, router.claude, get_settings()))
    return Pipeline(get_store(), router, Translator(router.small, router.claude), get_boundaries())
