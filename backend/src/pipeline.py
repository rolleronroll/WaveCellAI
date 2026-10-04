# Inbound SMS -> Router -> Translator -> GSM Enforcer -> Outbound pipeline

"""Inbound SMS -> language -> intent -> retrieval -> answer -> GSM-7 reply."""

from __future__ import annotations

from dataclasses import dataclass

from .analysis import IntentResult, classify
from .api.schemas import Intent, Tier
from .gateway import enforce_sms
from .rag import KnowledgeStore, retrieve
from .router import Router
from .translation import Translator, detect_language, romanize
from .geo import BoundaryRegistry, format_position_reply, parse_coords
from .rag.retriever import country_from_phone
import re

_COORD_HINT = re.compile(r"-?\d{1,3}\.\d+\s*[,\s]\s*-?\d{1,3}\.\d+")

_PRIORITY = {"emergency": 6, "operator": 5, "cyclone": 4, "position": 4, "transit": 3, "ferry": 3, "tide": 3, "faq": 2, "unknown": 1}

@dataclass(frozen=True)
class PipelineResult:
    reply: str
    septets: int
    bytes_used: int
    original_bytes: int
    segments: int
    truncated: bool
    intent: Intent
    tier: Tier
    escalated: bool
    confidence: float | None
    reason: str
    model: str | None
    lang: str
    english_query: str | None
    needs_alert: bool
    needs_operator: bool


class Pipeline:
    def __init__(self, store: KnowledgeStore, router: Router, translator: Translator, boundaries: BoundaryRegistry) -> None:
        self.store = store
        self.router = router
        self.translator = translator
        self.boundaries = boundaries


    @staticmethod
    def _pick_intent(question: str, english: str, command: str | None) -> IntentResult:
        candidates = [classify(question, command)]
        if english != question:
            candidates.append(classify(english, command))
        # An emergency in either version wins.
        return max(candidates, key=lambda c: (_PRIORITY[c.intent], c.confidence))

    async def run(
        self,
        phone: str,
        body: str,
        command: str | None = None,
        args: str = "",
        allow_claude: bool = True,
    ) -> PipelineResult:
        question = args or body
        lang = detect_language(question)


        english = question
        if lang.lang != "en":
            english = (await self.translator.to_english(question, lang.lang, allow_claude)).text

        # if command == "LOC" or (await self._is_position(question)):
        #     return self._position_result(phone, question, lang.lang)

        intent = self._pick_intent(question, english, command)

        wants_position = intent.intent != "emergency" and (
            command == "LOC" or intent.intent == "position" or bool(_COORD_HINT.search(english))
        )
        if wants_position:
        # if intent.intent == "position":
            coords = parse_coords(english)
            if coords is None:
                text = "Could not read coordinates. Text LOC 21.43,91.97 (lat,lon)."
            else:
                result = self.boundaries.locate(coords.lon, coords.lat)
                text = format_position_reply(result, country_from_phone(phone))
            sms = enforce_sms(text)
            return PipelineResult(
                reply=sms.text, septets=sms.septets, bytes_used=sms.bytes_used,
                original_bytes=sms.original_bytes, segments=sms.segments, truncated=sms.truncated,
                intent="position", tier="template", escalated=False, confidence=1.0,
                reason="position lookup", model=None, lang=lang.lang, english_query=None,
                needs_alert=False, needs_operator=False,
            )

        retrieval = await retrieve(self.store, intent.intent, english, phone=phone)
        routed = await self.router.answer(
            intent.intent, english, retrieval,
            allow_claude=allow_claude, lang=lang.lang, style=lang.style,
        )

        text = routed.text if lang.style == "native" else romanize(routed.text)
        sms = enforce_sms(text)

        return PipelineResult(
            reply=sms.text,
            septets=sms.septets,
            bytes_used=sms.bytes_used,
            original_bytes=sms.original_bytes,
            segments=sms.segments,
            truncated=sms.truncated,
            intent=intent.intent,
            tier=routed.tier,
            escalated=routed.escalated,
            confidence=routed.confidence,
            reason=routed.reason,
            model=routed.model,
            lang=lang.lang,
            english_query=english if lang.lang != "en" else None,
            needs_alert=intent.intent == "emergency",
            needs_operator=intent.intent == "operator",
        )