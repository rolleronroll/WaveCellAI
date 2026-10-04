"""Demo relay for the judge page: translate a message, and for SMS enforce the size limit + footer."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..deps import get_router
from ..gateway.sms_enforcer import enforce_sms   # adjust to wherever enforce_sms lives

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


router = APIRouter(prefix="/api/demo")

LANGS = {
    "en": "English",
    "bn": "Bengali written in English (Latin) letters (Banglish)",
    "hi": "Hindi written in English (Latin) letters (Hinglish)",
}


class RelayIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    target_lang: str = "en"
    as_sms: bool = False
    footer: str = ""          # sender's phone number, appended as "From:<number>"


@router.post("/relay")
async def relay(body: RelayIn) -> dict:
    text, note = body.text, ""
    try:
        res = await get_router().small.generate(
            f"Translate the user's message into {LANGS.get(body.target_lang, 'English')}. "
            "If it is already in that language, return it unchanged. Output only the translation.",
            body.text,
            max_tokens=300,
        )
        text = res.text.strip() or body.text
    except Exception:  # noqa: BLE001  demo only: show the original instead of failing
        note = "translation unavailable, original shown"

    out: dict = {"text": text, "translated": not note, "note": note}
    if body.as_sms:
        foot = f"\nFrom:{body.footer}" if body.footer else ""
        sms = enforce_sms(text, max_septets=160 - len(foot), max_ucs2=70 - len(foot))
        n = sms.septets + len(foot)
        out.update(
            text=sms.text + foot, septets=n, segments=sms.segments, encoding=sms.encoding,
            bytes_used=n * 2 if sms.encoding == "ucs2" else (n * 7 + 7) // 8,
        )
    return out
