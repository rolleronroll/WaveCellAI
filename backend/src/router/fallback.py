"""Template -> Gemini -> Claude router for SMS answers."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from ..api.schemas import Tier
from ..config import Settings, get_settings
from ..rag.prompts import build_user_prompt, split_self_rating, system_for
from ..rag.retriever import Retrieval
from .claude_client import ClaudeClient
from .confidence_eval import evaluate
from .errors import LLMError

log = logging.getLogger(__name__)

UNAVAILABLE = "Sorry, I cannot answer right now. Text OP to reach an operator."
UNCLEAR = "Sorry, I did not understand. Text a question, e.g. BUS Dhaka to Coxs Bazar."
EMERGENCY_NO_DATA = "EMERGENCY: call your local emergency number now. Move somewhere safe."
OPERATOR_ACK = "Your request was passed to an operator. Please wait for a reply here."

_WS = re.compile(r"\s+")


@dataclass(frozen=True)
class RoutedAnswer:
    text: str
    tier: Tier
    escalated: bool
    confidence: float | None
    reason: str
    model: str | None


def _tidy(text: str) -> str:
    return _WS.sub(" ", text).strip().strip('"')


class Router:
    def __init__(self, small, claude: ClaudeClient, settings: Settings | None = None) -> None:
        self.small = small
        self.claude = claude
        self.s = settings or get_settings()

    async def answer(
        self,
        intent: str,
        question: str,
        retrieval: Retrieval,
        allow_claude: bool = True,
        style: str = "romanized",
        lang: str = "en",
    ) -> RoutedAnswer:
        if retrieval.direct_answer:
            return RoutedAnswer(retrieval.direct_answer, "template", False, 1.0, "direct answer", None)
        if intent == "emergency":
            return RoutedAnswer(EMERGENCY_NO_DATA, "template", False, None, "no emergency contacts", None)
        if intent == "operator":
            return RoutedAnswer(OPERATOR_ACK, "template", False, None, "operator request", None)
        if intent == "unknown":
            return RoutedAnswer(UNCLEAR, "template", False, None, "unclear message", None)

        user_prompt = build_user_prompt(question, retrieval.context)

        why = ""
        try:
            res = await self.small.generate(system_for(lang, style), user_prompt, max_tokens=256)
            text, rating = split_self_rating(res.text)
            conf = evaluate(text, retrieval.top_score, rating, self.s.confidence_threshold)
            if not conf.escalate:
                return RoutedAnswer(_tidy(text), "small", False, conf.score, conf.reason, res.model)
            why = f"low confidence ({conf.score}: {conf.reason})"
        except LLMError as exc:
            why = f"small model failed: {exc}"

        log.info("Escalating to Claude: %s", why)

        if not allow_claude:
            return RoutedAnswer(UNAVAILABLE, "template", True, None, f"{why}; claude not allowed", None)
        try:
            text = await self.claude.generate(system_for(lang, style, fallback=True), user_prompt, max_tokens=256)
        except LLMError as exc:
            return RoutedAnswer(UNAVAILABLE, "template", True, None, f"{why}; claude failed: {exc}", None)
        return RoutedAnswer(_tidy(text), "claude", True, None, why, self.s.claude_model)