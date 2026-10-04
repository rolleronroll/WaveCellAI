"""Small-model tier: Google Gemini Flash via the REST API (no SDK needed)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx

from ..config import Settings, get_settings
from .errors import LLMError

_BASE = "https://generativelanguage.googleapis.com/v1beta"
_RETRY_STATUS = (500, 502, 503, 504)


@dataclass(frozen=True)
class SmallResult:
    text: str
    model: str
    finish_reason: str | None = None
    thought_tokens: int | None = None


class GeminiLLM:
    def __init__(self, settings: Settings | None = None) -> None:
        self.s = settings or get_settings()
        self._client = httpx.AsyncClient(
            base_url=_BASE,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.s.google_api_key,
            },
            timeout=httpx.Timeout(self.s.gemini_timeout_s, connect=10.0),
        )

    async def generate(
        self,
        system: str,
        user: str,
        max_tokens: int = 300,
        temperature: float = 0.2,
    ) -> SmallResult:
        gen_cfg: dict = {"maxOutputTokens": max_tokens, "temperature": temperature}
        if self.s.gemini_thinking_level:
            gen_cfg["thinkingConfig"] = {"thinkingLevel": self.s.gemini_thinking_level}

        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": gen_cfg,
        }

        attempts = 2
        resp = None
        for attempt in range(attempts):
            try:
                resp = await self._client.post(
                    f"/models/{self.s.gemini_model}:generateContent", json=payload
                )
                resp.raise_for_status()
                break
            except httpx.TimeoutException as exc:
                # A slow model will not get faster on retry. Fail fast so the router
                # can answer with Claude instead of making the user wait.
                raise LLMError(
                    f"Gemini timed out after {self.s.gemini_timeout_s:.0f}s ({type(exc).__name__})"
                ) from exc
            except httpx.HTTPStatusError as exc:
                code = exc.response.status_code
                if code not in _RETRY_STATUS or attempt == attempts - 1:
                    raise LLMError(f"Gemini HTTP {code}") from exc
            except httpx.HTTPError as exc:
                raise LLMError(f"Gemini unreachable: {type(exc).__name__}: {exc}") from exc
            await asyncio.sleep(1.0)

        data = resp.json()
        cands = data.get("candidates") or []
        if not cands:
            reason = (data.get("promptFeedback") or {}).get("blockReason", "unknown")
            raise LLMError(f"Gemini returned no candidates (blockReason={reason})")

        cand = cands[0]
        finish = cand.get("finishReason")
        thoughts = (data.get("usageMetadata") or {}).get("thoughtsTokenCount")
        parts = (cand.get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()

        if finish == "MAX_TOKENS":
            # A cut-off reply must never reach a user: treat it as a failure.
            raise LLMError(
                f"Gemini hit max_tokens={max_tokens} (thinking used {thoughts}); reply was cut off"
            )
        if not text:
            raise LLMError(f"Gemini returned no text (finishReason={finish})")
        return SmallResult(
            text=text,
            model=self.s.gemini_model,
            finish_reason=finish,
            thought_tokens=thoughts,
        )

    async def healthy(self) -> bool:
        return bool(self.s.google_api_key)

    async def aclose(self) -> None:
        await self._client.aclose()

#         """Small-model tier: Google Gemini Flash via the REST API (no SDK needed)."""
#
# from __future__ import annotations
#
# from dataclasses import dataclass
#
# import httpx
#
# from ..config import Settings, get_settings
# from .errors import LLMError
#
# _BASE = "https://generativelanguage.googleapis.com/v1beta"
#
#
# @dataclass(frozen=True)
# class SmallResult:
#     text: str
#     model: str
#
#
# class GeminiLLM:
#     def __init__(self, settings: Settings | None = None) -> None:
#         self.s = settings or get_settings()
#         self._client = httpx.AsyncClient(
#             base_url=_BASE,
#             headers={
#                 "Content-Type": "application/json",
#                 "x-goog-api-key": self.s.google_api_key,  # header keeps the key out of URLs/logs
#             },
#             timeout=self.s.gemini_timeout_s,
#         )
#
#     async def generate(
#             self,
#             system: str,
#             user: str,
#             max_tokens: int = 120,
#             temperature: float = 0.2,
#     ) -> SmallResult:
#         gen_cfg: dict = {"maxOutputTokens": max_tokens, "temperature": temperature}
#         if self.s.gemini_thinking_level:
#             gen_cfg["thinkingConfig"] = {"thinkingLevel": self.s.gemini_thinking_level}
#
#         payload = {
#             "systemInstruction": {"parts": [{"text": system}]},
#             "contents": [{"role": "user", "parts": [{"text": user}]}],
#             "generationConfig": gen_cfg,
#         }
#         try:
#             resp = await self._client.post(
#                 f"/models/{self.s.gemini_model}:generateContent", json=payload
#             )
#             resp.raise_for_status()
#         except httpx.HTTPStatusError as exc:
#             # 429 = free-tier rate limit; the router treats any LLMError as "escalate"
#             raise LLMError(f"Gemini HTTP {exc.response.status_code}") from exc
#         except httpx.HTTPError as exc:
#             raise LLMError(f"Gemini unreachable: {exc}") from exc
#         data = resp.json()
#
#         cands = data.get("candidates") or []
#         if not cands:
#             reason = (data.get("promptFeedback") or {}).get("blockReason", "unknown")
#             raise LLMError(f"Gemini returned no candidates (blockReason={reason})")
#
#         cand = cands[0]
#         parts = (cand.get("content") or {}).get("parts") or []
#         text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
#         if not text:
#             raise LLMError(f"Gemini returned no text (finishReason={cand.get('finishReason')})")
#         return SmallResult(text=text, model=self.s.gemini_model)
#
#         # data = resp.json()
#         # try:
#         #     parts = data["candidates"][0]["content"]["parts"]
#         # except (KeyError, IndexError) as exc:
#         #     raise LLMError("Gemini returned no candidates (possibly blocked)") from exc
#         #
#         # text = "".join(p.get("text", "") for p in parts).strip()
#         # if not text:
#         #     raise LLMError("Gemini returned empty text")
#         # return SmallResult(text=text, model=self.s.gemini_model)
#     #
#     # async def healthy(self) -> bool:
#     #     return bool(self.s.google_api_key)
#     #
#     # async def aclose(self) -> None:
#     #     await self._client.aclose()
