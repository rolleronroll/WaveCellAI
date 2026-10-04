"""Parse and sanitise inbound SMS payloads from the Android gateway."""

from __future__ import annotations

import hashlib
import hmac
import re
import unicodedata
from dataclasses import dataclass

MAX_BODY_CHARS = 1000
COMMANDS = frozenset({"SOS", "BUS", "OP", "INFO", "FERRY", "TIDE", "SIGNAL","LOC"})

_PHONE_STRIP = re.compile(r"[^\d+]")
_PHONE_OK = re.compile(r"\+\d{7,15}")
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WS = re.compile(r"\s+")


class ParseError(ValueError):
    """Inbound payload is unusable (bad sender, empty body, ...)."""


@dataclass(frozen=True)
class ParsedSms:
    message_id: str
    phone: str                 # normalised to +<country><number>
    body: str                  # cleaned text
    command: str | None        # "SOS" | "BUS" | "OP" | "INFO" | None
    args: str                  # body without the command word
    received_at_ms: int | None
    input_truncated: bool


def verify_gateway_secret(provided: str | None, expected: str) -> bool:
    """Constant-time comparison of the X-Gateway-Secret header."""
    if not provided or not expected:
        return False
    return hmac.compare_digest(provided.encode(), expected.encode())


def normalize_phone(raw: str, default_country_code: str = "880") -> str:
    """Normalise to E.164-style. Alphanumeric sender IDs (e.g. 'bKash') are rejected."""
    s = _PHONE_STRIP.sub("", raw.strip())
    if s.startswith("00"):
        s = "+" + s[2:]
    elif s.startswith("0") and default_country_code:
        s = "+" + default_country_code + s[1:]   # local format, e.g. 01712345678
    elif not s.startswith("+"):
        s = "+" + s                              # assume the country code is present
    if not _PHONE_OK.fullmatch(s):
        raise ParseError(f"Invalid sender number: {raw!r}")
    return s


def clean_body(body: str) -> tuple[str, bool]:
    text = unicodedata.normalize("NFC", body)
    text = _CTRL.sub("", text)
    text = _WS.sub(" ", text).strip()
    if len(text) > MAX_BODY_CHARS:
        return text[:MAX_BODY_CHARS], True
    return text, False


def _split_command(text: str) -> tuple[str | None, str]:
    first, _, rest = text.partition(" ")
    word = first.rstrip(":,.!").upper()
    if word in COMMANDS:
        return word, rest.strip()
    return None, text


def _fallback_id(phone: str, body: str, received_at_ms: int | None) -> str:
    raw = f"{phone}|{received_at_ms or ''}|{body}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def parse_inbound(
    sender: str,
    body: str,
    message_id: str | None = None,
    received_at_ms: int | None = None,
    default_country_code: str = "880",
) -> ParsedSms:
    phone = normalize_phone(sender, default_country_code)
    text, truncated = clean_body(body)
    if not text:
        raise ParseError("Empty message body")
    command, args = _split_command(text)
    return ParsedSms(
        message_id=message_id or _fallback_id(phone, text, received_at_ms),
        phone=phone,
        body=text,
        command=command,
        args=args,
        received_at_ms=received_at_ms,
        input_truncated=truncated,
    )

# Parses incoming SMS headers & phone numbers