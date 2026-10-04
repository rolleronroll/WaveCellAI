"""Try the primary Gemini model; on any LLMError try the backup Gemini model."""

import logging

from .errors import LLMError

log = logging.getLogger(__name__)


class ModelFallbackLLM:
    def __init__(self, primary, secondary) -> None:
        self.primary = primary
        self.secondary = secondary

    async def generate(self, *args, **kwargs):
        try:
            return await self.primary.generate(*args, **kwargs)
        except LLMError as exc:
            log.info("Primary Gemini failed (%s); trying backup model", exc)
            return await self.secondary.generate(*args, **kwargs)