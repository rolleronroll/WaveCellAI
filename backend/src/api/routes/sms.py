# Android SMS Gateway incoming/outgoing webhook endpoints

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request

from ... import state
from ...config import get_settings
from ...deps import get_pipeline
from ...gateway import ParseError, parse_inbound, verify_gateway_secret
from ...pipeline import PipelineResult
from ..schemas import ChatRequest, InboundSms, SmsReply

router = APIRouter(prefix="/api/sms", tags=["sms"])


class SimulateReply(SmsReply):
    lang: str
    reason: str
    english_query: str | None = None
    confidence: float | None = None
    model: str | None = None


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _run(phone: str, body: str, command: str | None, args: str) -> PipelineResult:
    allow_claude = state.claude_budget.has_room()
    result = await get_pipeline().run(phone, body, command, args, allow_claude=allow_claude)
    if result.tier == "claude":
        state.claude_budget.take()
    state.log_event(
        intent=result.intent, tier=result.tier, lang=result.lang, escalated=result.escalated,
        septets=result.septets, bytes_used=result.bytes_used, original_bytes=result.original_bytes,
    )
    return result


def _reply_fields(to: str, r: PipelineResult, in_reply_to: str | None) -> dict:
    return dict(
        to=to, body=r.reply, septets=r.septets, bytes_used=r.bytes_used, segments=r.segments,
        intent=r.intent, tier=r.tier, escalated=r.escalated, in_reply_to=in_reply_to,
    )


@router.post("/inbound", response_model=SmsReply)
async def inbound(msg: InboundSms, x_gateway_secret: str | None = Header(default=None)) -> SmsReply:
    s = get_settings()
    if s.gateway_shared_secret == "change-me":
        raise HTTPException(503, "Gateway secret is not configured")
    if not verify_gateway_secret(x_gateway_secret, s.gateway_shared_secret):
        raise HTTPException(401, "Invalid gateway secret")
    try:
        parsed = parse_inbound(msg.sender, msg.body, msg.message_id, msg.received_at_ms)
    except ParseError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not state.limiter_phone.allow(parsed.phone):
        raise HTTPException(429, "Too many messages from this number")

    result = await _run(parsed.phone, parsed.body, parsed.command, parsed.args)
    return SmsReply(**_reply_fields(parsed.phone, result, parsed.message_id))


@router.post("/simulate", response_model=SimulateReply)
async def simulate(req: ChatRequest, request: Request) -> SimulateReply:
    if not state.limiter_ip.allow(_client_ip(request)):
        raise HTTPException(429, "Too many messages. Wait a minute and try again.")
    try:
        parsed = parse_inbound(req.phone, req.message)
    except ParseError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not state.limiter_phone.allow(parsed.phone):
        raise HTTPException(429, "Too many messages. Try again later.")

    result = await _run(parsed.phone, parsed.body, parsed.command, parsed.args)
    return SimulateReply(
        **_reply_fields(parsed.phone, result, parsed.message_id),
        lang=result.lang, reason=result.reason, english_query=result.english_query,
        confidence=result.confidence, model=result.model,
    )