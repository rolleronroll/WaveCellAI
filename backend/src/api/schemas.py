"""Pydantic models shared by the API routes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
Intent = Literal["transit", "ferry", "tide", "cyclone", "emergency", "faq", "operator", "unknown", "position"]
Tier = Literal["template", "small", "claude"]


# ---------- Android gateway <-> backend ----------
class InboundSms(BaseModel):
    message_id: str | None = Field(default=None, max_length=64)
    sender: str = Field(min_length=3, max_length=32)
    body: str = Field(min_length=1, max_length=2000)
    received_at_ms: int | None = None
    sim_slot: int | None = None


class SmsReply(BaseModel):
    """What the gateway should send back over the cellular network."""
    to: str
    body: str
    septets: int
    bytes_used: int
    segments: int
    intent: Intent
    tier: Tier
    escalated: bool = False        # True if the small model fell back to Claude
    in_reply_to: str | None = None


# ---------- Web operator chat (SSE) ----------
class ChatRequest(BaseModel):
    phone: str = Field(min_length=3, max_length=32)
    message: str = Field(min_length=1, max_length=1000)


class ChatEvent(BaseModel):
    event: Literal["status", "token", "final", "error"]
    data: str


# ---------- Emergency ----------
class EmergencyAlert(BaseModel):
    id: int
    phone: str
    message: str
    location_hint: str | None = None
    status: Literal["open", "acknowledged", "resolved"] = "open"
    created_at: str


class EmergencyUpdate(BaseModel):
    status: Literal["acknowledged", "resolved"]


# ---------- Schedules ----------
class BusQuery(BaseModel):
    origin: str = Field(min_length=2, max_length=64)
    destination: str = Field(min_length=2, max_length=64)
    after: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    limit: int = Field(default=3, ge=1, le=10)


class BusDeparture(BaseModel):
    route: str
    origin: str
    destination: str
    departs: str
    days: str
    fare: str | None = None
    duration_min: int | None = None
    tomorrow: bool = False


# ---------- Users / sessions ----------
class UserSession(BaseModel):
    phone: str
    language: str | None = None
    message_count: int = 0
    last_seen: str | None = None


# ---------- Metrics ----------
class MetricsSummary(BaseModel):
    total_messages: int
    total_septets: int
    total_bytes_sent: int
    avg_bytes_per_reply: float
    escalation_rate: float                 # share of replies answered by Claude
    estimated_sms_cost_usd: float
    estimated_roaming_data_cost_usd: float  # what the same answers would cost as roaming data
    estimated_savings_usd: float# Pydantic validation schemas