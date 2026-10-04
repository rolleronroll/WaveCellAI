"""Language and script helpers for Hinglish and Banglish SMS. No models needed.

Detection uses Unicode ranges plus small starter word lists: extend them from real
messages. Romanization is a rough safety net (unidecode), because the LLM is told to
reply in Latin letters already.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from unidecode import unidecode

_BENGALI = re.compile(r"[\u0980-\u09FF]")
_DEVANAGARI = re.compile(r"[\u0900-\u097F]")
_WORD = re.compile(r"[a-z]+")
_VOWEL_RUN = re.compile(r"([aiu])\1+")
_JUNK = re.compile(r'[^A-Za-z0-9 .,;:!?\'"()+\-/@%&*#=<>\n]')

# Starter lists. Words that are also common English words are left out on purpose.
BN_WORDS = frozenset("""
ami amar amake tumi tomar apni apnar kothay kothaye koto kemon kobe kokhon keno
ache nei nai hobe jabo jabe jete theke dorkar lagbe bhai vai thik bhalo kharap
sokal bikel aj kal taka pani bari rasta gari nouka bachao shahajjo sahajjo bipod
jaoa jacche dube
""".split())

HI_WORDS = frozenset("""
mujhe mera meri mere hai hain kya kaise kahan kab kitna kitne nahi nahin chahiye
aap tum hum mein se ko ka ke ki theek accha acha bahut madad bachao paani raasta
gaadi ghar abhi aaj kal baje baad paisa rupaye yaar bhai
""".split())


@dataclass(frozen=True)
class LangInfo:
    lang: str        # "en" | "bn" | "hi"
    style: str       # "english" | "native" | "romanized"
    confidence: float


def detect_language(text: str) -> LangInfo:
    bn_chars = len(_BENGALI.findall(text))
    hi_chars = len(_DEVANAGARI.findall(text))
    if bn_chars or hi_chars:
        return LangInfo("bn" if bn_chars >= hi_chars else "hi", "native", 1.0)

    tokens = _WORD.findall(text.lower())
    if not tokens:
        return LangInfo("en", "english", 0.5)

    bn_hits = sum(t in BN_WORDS for t in tokens)
    hi_hits = sum(t in HI_WORDS for t in tokens)
    hits, lang = (bn_hits, "bn") if bn_hits >= hi_hits else (hi_hits, "hi")  # tie -> Bengali
    ratio = hits / len(tokens)
    if hits >= 2 or (hits >= 1 and ratio >= 0.2):
        return LangInfo(lang, "romanized", round(min(1.0, ratio * 2), 2))
    return LangInfo("en", "english", round(1.0 - ratio, 2))


def romanize(text: str) -> str:
    """Native Bengali/Devanagari to rough Latin letters. Latin text passes through."""
    if not (_BENGALI.search(text) or _DEVANAGARI.search(text)):
        return text
    out: list[str] = []
    for part in re.split(r"(\s+)", text):
        if _BENGALI.search(part) or _DEVANAGARI.search(part):
            part = _VOWEL_RUN.sub(r"\1", unidecode(part).lower())
            part = _JUNK.sub("", part)
        out.append(part)
    return "".join(out).strip()


# --- AI4Bharat IndicXlit / Bhashini (DISABLED, not wired in) -------------------------
# Roman <-> native script transliteration needs either a Bhashini account (API key,
# endpoint, service ID) or a host running IndicXlit. The request format is deliberately
# not written here: verify it against the Bhashini docs first, then implement
# `async def xlit(text, lang, direction)` and select it with INDIC_PROVIDER=bhashini.