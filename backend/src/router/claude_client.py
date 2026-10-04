"""Fallback tier: Claude, used for low-confidence answers and emergencies."""

from __future__ import annotations

from anthropic import AsyncAnthropic, APIError

from ..config import Settings, get_settings
from .errors import LLMError


class ClaudeClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.s = settings or get_settings()
        self._client = AsyncAnthropic(
            api_key=self.s.anthropic_api_key,
            timeout=self.s.claude_timeout_s,
        )

    async def generate(
        self,
        system: str,
        user: str,
        max_tokens: int = 120,
        # temperature: float = 0.2,
    ) -> str:
        try:
            msg = await self._client.messages.create(
                model=self.s.claude_model,
                max_tokens=max_tokens,
                # temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except APIError as exc:
            raise LLMError(f"Claude API error: {exc}") from exc

        text = "".join(b.text for b in msg.content if b.type == "text").strip()
        if not text:
            raise LLMError("Claude returned empty text")
        return text

    async def aclose(self) -> None:
        await self._client.close()