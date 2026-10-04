# SMS payload enforcement: GSM 7-bit (160 septets) for Latin text,
# UCS-2 (70 UTF-16 units) for Bengali / Devanagari script.

import re
import unicodedata
from dataclasses import dataclass

# GSM 7-bit basic character set definitions
GSM_BASIC_CHARS = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ\x1bÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)

# GSM 7-bit extension characters (each counts as 2 septets)
GSM_EXTENDED_CHARS = set("^{}\\[~]|€")

# Native scripts that cannot be sent as GSM-7
_NATIVE_SCRIPT = re.compile(r"[\u0900-\u097F\u0980-\u09FF]")

UCS2_SINGLE = 70   # UTF-16 units in one unsegmented UCS-2 SMS
UCS2_MULTI = 67    # units per part when a UCS-2 message is split

_VIRAMA = {"\u094d", "\u09cd"}   # Devanagari, Bengali: a cut after one leaves a broken glyph
_JOINERS = {"\u200c", "\u200d"}


@dataclass(frozen=True)
class EnforcedSms:
    """Payload metrics. For encoding='ucs2', `septets` holds UTF-16 units."""

    text: str
    septets: int
    bytes_used: int
    original_bytes: int
    segments: int
    truncated: bool
    encoding: str = "gsm7"


def count_gsm_septets(text: str) -> int:
    """Total GSM 7-bit septets required for the text string."""
    septets = 0
    for char in text:
        if char in GSM_BASIC_CHARS:
            septets += 1
        elif char in GSM_EXTENDED_CHARS:
            septets += 2
        else:
            septets += 1
    return septets


def count_ucs2_units(text: str) -> int:
    """UTF-16 code units (what a UCS-2 SMS actually counts)."""
    return len(text.encode("utf-16-le")) // 2


def _cut_ucs2(text: str, max_units: int) -> str:
    """Trim to max_units without splitting a conjunct or a base+vowel-sign pair."""
    ell = "..."
    budget = max_units - len(ell)
    out = text
    while out and count_ucs2_units(out) > budget:
        out = out[:-1]
    # If the next character (the first one dropped) is a combining mark or joiner,
    # its base letter would be left dangling, so drop that base too.
    while out and len(out) < len(text) and (
        unicodedata.category(text[len(out)]).startswith("M") or text[len(out)] in _JOINERS
    ):
        out = out[:-1]
    # Never end on a virama or joiner.
    while out and (out[-1] in _VIRAMA or out[-1] in _JOINERS):
        out = out[:-1]
    return out.rstrip() + ell


def _enforce_ucs2(text: str, original_bytes: int, max_units: int, footer: str) -> EnforcedSms:
    clean = unicodedata.normalize("NFC", text).strip()
    if footer:
        clean = f"{clean}\nFrom:{footer}"

    truncated = False
    if count_ucs2_units(clean) > max_units:
        truncated = True
        clean = _cut_ucs2(clean, max_units)

    units = count_ucs2_units(clean)
    segments = 1 if units <= UCS2_SINGLE else -(-units // UCS2_MULTI)
    return EnforcedSms(
        text=clean,
        septets=units,
        bytes_used=units * 2,
        original_bytes=original_bytes,
        segments=segments,
        truncated=truncated,
        encoding="ucs2",
    )


def enforce_sms(
    text: str,
    max_septets: int = 160,
    footer: str = "",
    max_ucs2: int = UCS2_SINGLE,
) -> EnforcedSms:
    """
    Enforce a single-segment SMS.

    Latin text: GSM 7-bit, 160 septets = 140 bytes.
    Bengali / Devanagari script: UCS-2, 70 characters = 140 bytes.
    """
    original_bytes = len(text.encode("utf-8"))

    if _NATIVE_SCRIPT.search(text):
        return _enforce_ucs2(text, original_bytes, max_ucs2, footer)

    # Convert non-GSM characters into ASCII representations
    clean_text = unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode("utf-8")

    if footer:
        clean_text = f"{clean_text}\nFrom:{footer}"

    current_septets = count_gsm_septets(clean_text)
    truncated = False

    if current_septets > max_septets:
        truncated = True
        while clean_text and count_gsm_septets(clean_text + "...") > max_septets:
            clean_text = clean_text[:-1]
        clean_text = clean_text + "..."
        current_septets = count_gsm_septets(clean_text)

    bytes_used = (current_septets * 7 + 7) // 8
    segments = 1 if current_septets <= 160 else (current_septets + 152) // 153

    return EnforcedSms(
        text=clean_text,
        septets=current_septets,
        bytes_used=bytes_used,
        original_bytes=original_bytes,
        segments=segments,
        truncated=truncated,
        encoding="gsm7",
    )