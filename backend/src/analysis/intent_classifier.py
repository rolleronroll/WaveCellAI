"""Rule-based SMS intent classifier (no model call, works offline)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..api.schemas import Intent

_COMMAND_INTENT: dict[str, Intent] = {
    "SOS": "emergency",
    "BUS": "transit",
    "FERRY": "ferry",
    "TIDE": "tide",
    "SIGNAL": "cyclone",
    "OP": "operator",
    "INFO": "faq",
    "LOC": "position",
}

_EMERGENCY_EN = re.compile(
    r"\b(sos|emergency|ambulance|accident|injur\w*|bleeding|unconscious|heart attack|"
    r"drown\w*|robbed|robbery|mugged|attacked|assault\w*|kidnap\w*|on fire|fire)\b",
    re.I,
)

_COORD_HINT = re.compile(r"-?\d{1,3}\.\d+\s*[,\s]\s*-?\d{1,3}\.\d+")

_EMERGENCY_LOCAL = re.compile(
    r"\b(bachao|bachaao|shahajjo|sahajjo|durghotona|agun)\b"
    r"|বাঁচাও|বাচাও|সাহায্য|দুর্ঘটনা|আগুন|অ্যাম্বুলেন্স",
    re.I,
)
_HELP_ALONE = re.compile(r"^\W*(please\s+)?help(\s+me)?\W*$", re.I)

_OPERATOR = re.compile(
    r"\b(operator|human|real person|customer (service|support)|talk to (a |an )?(person|agent|someone))\b",
    re.I,
)
_FERRY = re.compile(
    r"\b(ferry|ferries|launch|launches|lonch|steamer|speedboat|speed boat|water ?bus|biwtc|biwta)\b",
    re.I,
)
_TIDE = re.compile(
    r"\b(tide|tides|high tide|low tide|water level|jowar|bhata|jowar bhata)\b"
    r"|জোয়ার|ভাটা",
    re.I,
)
_CYCLONE = re.compile(
    r"\b(cyclone|signal|storm warning|typhoon|sanket|shongket|mohasotorko)\b"
    r"|সংকেত",
    re.I,
)
_TRANSIT = re.compile(
    r"\b(bus(es)?|bas|coach|schedule|timetable|depart\w*|train|route|fare|ticket)\b",
    re.I,
)
_ROUTE_PATTERN = re.compile(r"\bfrom\s+\S+(\s+\S+)?\s+to\s+\S+", re.I)


@dataclass(frozen=True)
class IntentResult:
    intent: Intent
    confidence: float
    reason: str


def classify(body: str, command: str | None = None) -> IntentResult:
    """Classify an inbound SMS. `command` comes from payload_parser."""
    if command in _COMMAND_INTENT:
        return IntentResult(_COMMAND_INTENT[command], 1.0, f"command:{command}")

    text = body.strip()
    if sum(c.isalnum() for c in text) < 2:
        return IntentResult("unknown", 0.0, "no content")

    if _HELP_ALONE.match(text) or _EMERGENCY_EN.search(text) or _EMERGENCY_LOCAL.search(text):
        return IntentResult("emergency", 0.95, "emergency keyword")
    if _OPERATOR.search(text):
        return IntentResult("operator", 0.9, "operator keyword")
    if _COORD_HINT.search(text):
        return IntentResult("position", 0.9, "coordinate pattern")
    if _CYCLONE.search(text):
        return IntentResult("cyclone", 0.85, "cyclone keyword")
    if _FERRY.search(text):
        return IntentResult("ferry", 0.85, "ferry keyword")
    if _TIDE.search(text):
        return IntentResult("tide", 0.85, "tide keyword")
    if _TRANSIT.search(text):
        return IntentResult("transit", 0.85, "transit keyword")
    if _ROUTE_PATTERN.search(text):
        return IntentResult("transit", 0.7, "from-to pattern")
    return IntentResult("faq", 0.5, "default")