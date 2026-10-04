# """Local Ministral-8B-Instruct-2410 (Q4_K_M GGUF) served by llama.cpp's llama-server.
#
# DISABLED: needs a host you run (VPS/GPU box). Start it with:
#
#   llama-server -m Ministral-8B-Instruct-2410-Q4_K_M.gguf \
#     --host 0.0.0.0 --port 8080 -c 4096 --api-key YOUR_TOKEN
#
# Unlike Gemini, llama-server returns token
# """
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
#
# @dataclass(frozen=True)
# class LocalResult:
#     text: str
#     avg_logprob: float | None  # mean token logprob; None if the server omits it
#     model: str
#
#
# class LocalLLM:
#     def __init__(self, settings: Settings | None = None) -> None:
#         self.s = settings or get_settings()
#         headers = {"Content-Type": "application/json"}
#         if self.s.local_ai_token:
#             headers["Authorization"] = f"Bearer {self.s.local_ai_token}"
#         self._client = httpx.AsyncClient(
#             base_url=self.s.local_ai_url.rstrip("/"),
#             headers=headers,
#             timeout=self.s.local_ai_timeout_s,
#         )
#
#     async def generate(
#         self,
#         system: str,
#         user: str,
#         max_tokens: int = 80,
#         temperature: float = 0.2,
#     ) -> LocalResult:
#         payload = {
#             "model": self.s.local_ai_model,
#             "messages": [
#                 {"role": "system", "content": system},
#                 {"role": "user", "content": user},
#             ],
#             "max_tokens": max_tokens,
#             "temperature": temperature,
#             "logprobs": True,
#         }
#         try:
#             resp = await self._client.post("/v1/chat/completions", json=payload)
#             resp.raise_for_status()
#         except httpx.HTTPError as exc:
#             raise LLMError(f"Local model unreachable: {exc}") from exc
#
#         choice = resp.json()["choices"][0]
#         text = (choice["message"]["content"] or "").strip()
#
#         avg_lp: float | None = None
#         tokens = (choice.get("logprobs") or {}).get("content") or []
#         lps = [t["logprob"] for t in tokens if "logprob" in t]
#         if lps:
#             avg_lp = sum(lps) / len(lps)
#
#         return LocalResult(text=text, avg_logprob=avg_lp, model=self.s.local_ai_model)
#
#     async def healthy(self) -> bool:
#         try:
#             r = await self._client.get("/health")
#             return r.status_code == 200
#         except httpx.HTTPError:
#             return False
#
#     async def aclose(self) -> None:
#         await self._client.aclose()