"""Hybrid retriever: structured SQLite lookups first, FTS5 text search second."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from .sqlite_store import BusDeparture, FerryDeparture, Hit, KnowledgeStore, TideEvent, query_terms

# Bangladesh has no daylight saving, so a fixed UTC+6 offset needs no tz database.
BD_TZ = timezone(timedelta(hours=6))
COUNTRY_BY_PREFIX = {"+880": "Bangladesh"}  # extend as you add countries

MAX_CONTEXT_CHARS = 900
MAX_SNIPPET_CHARS = 280
PLACE_MATCH_RATIO = 0.82
TODAY_WORDS = {"today", "aj", "ajke", "aaj"}
TOMORROW_WORDS = {"tomorrow", "kal", "agamikal"}
RIVER_WORDS = {"river", "nodi", "nodite"}
IMD_WORDS = {"imd", "india", "bharat"}
_SIGNAL_NUM = re.compile(r"\b(\d{1,2})\b")


@dataclass(frozen=True)
class Retrieval:
    context: str = ""  # compact text for the model prompt
    hits: tuple[Hit, ...] = ()
    top_score: float = 0.0  # best hit, 0..1 (1.0 for template answers)
    direct_answer: str | None = None  # ready-made reply: no model call needed
    buses: tuple[BusDeparture, ...] = field(default=())


def country_from_phone(phone: str | None) -> str | None:
    for prefix, country in COUNTRY_BY_PREFIX.items():
        if phone and phone.startswith(prefix):
            return country
    return None


# ---------- transit ----------
def _norm(s: str) -> str:
    s = s.lower().replace("'", "").replace("\u2019", "")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _find_places(query: str, places: list[str]) -> tuple[list[tuple[int, str]], list[str]]:
    """Find known places in the query, tolerating typos like 'cox bazar'."""
    tokens = _norm(query).split()
    found: list[tuple[int, str]] = []
    for place in places:
        target = _norm(place)
        n = len(target.split())
        for i in range(len(tokens) - n + 1):
            cand = " ".join(tokens[i: i + n])
            if SequenceMatcher(None, cand, target).ratio() >= PLACE_MATCH_RATIO:
                found.append((i, place))
                break
    found.sort()
    return found, tokens


def _find_single_place(query: str, places: list[str]) -> str | None:
    found, _ = _find_places(query, places)
    return found[0][1] if found else None


def pick_route(query: str, places: list[str]) -> tuple[str, str] | None:
    found, tokens = _find_places(query, places)
    if len(found) < 2:
        return None
    origin = dest = None
    for idx, place in found:
        prev = tokens[idx - 1] if idx > 0 else ""
        if prev == "from" and origin is None:
            origin = place
        elif prev == "to" and dest is None:
            dest = place
    ordered = [p for _, p in found]
    origin = origin or next((p for p in ordered if p != dest), None)
    dest = dest or next((p for p in ordered if p != origin), None)
    if origin and dest and origin != dest:
        return origin, dest
    return None


_HHMM = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
_AMPM = re.compile(r"\b(1[0-2]|0?[1-9])\s?(am|pm)\b", re.I)


def parse_time(query: str) -> str | None:
    m = _HHMM.search(query)
    if m:
        return f"{int(m[1]):02d}:{m[2]}"
    m = _AMPM.search(query)
    if m:
        hour = int(m[1]) % 12 + (12 if m[2].lower() == "pm" else 0)
        return f"{hour:02d}:00"
    return None


def _format_buses(origin: str, dest: str, after: str, buses: list[BusDeparture]) -> str:
    if not buses:
        return f"No buses found {origin} to {dest}. Text OP for help."
    when = "tomorrow" if buses[0].tomorrow else f"after {after}"
    times = ", ".join(b.departs for b in buses)
    fare = f" Fare {buses[0].fare}." if buses[0].fare else ""
    return f"{origin}->{dest} {when}: {times}.{fare}"


async def _transit(store: KnowledgeStore, query: str, now: datetime | None) -> Retrieval | None:
    route = pick_route(query, await store.bus_places())
    if route is None:
        return None  # no clear from/to: fall through to text search + model
    origin, dest = route
    after = parse_time(query) or (now or datetime.now(BD_TZ)).strftime("%H:%M")
    buses = await store.next_buses(origin, dest, after)
    answer = _format_buses(origin, dest, after, buses)
    return Retrieval(context=answer, top_score=1.0, direct_answer=answer, buses=tuple(buses))


# ---------- emergency ----------
async def _emergency(store: KnowledgeStore, phone: str | None) -> Retrieval:
    contacts = (await store.emergency(country_from_phone(phone)))[:4]
    if not contacts:
        return Retrieval()
    numbers = "; ".join(f"{c.number} ({c.service})" for c in contacts)
    answer = f"EMERGENCY: call {numbers} now."
    return Retrieval(context=answer, top_score=1.0, direct_answer=answer)


# ---------- text search ----------
def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _coverage(terms: list[str], text: str) -> float:
    """Share of query terms found in the text. Prefix matching tolerates plurals."""
    if not terms:
        return 0.0
    words = re.findall(r"\w+", text.lower())

    def found(t: str) -> bool:
        return any(
            (len(t) >= 3 and w.startswith(t)) or (len(w) >= 4 and t.startswith(w))
            for w in words
        )

    return sum(found(t) for t in terms) / len(terms)


# ---------- ferry ----------
def _format_ferries(origin: str, dest: str, after: str, ferries: list[FerryDeparture]) -> str:
    if not ferries:
        return f"No ferries/launches found {origin} to {dest}. Text OP for help."
    when = "tomorrow" if ferries[0].tomorrow else f"after {after}"
    times = ", ".join(f.departs for f in ferries)
    kind = ferries[0].vessel_type or "ferry"
    fare = f" Fare {ferries[0].fare}." if ferries[0].fare else ""
    return f"{origin}->{dest} {kind} {when}: {times}.{fare}"


async def _ferry(store: KnowledgeStore, query: str, now: datetime | None) -> Retrieval | None:
    route = pick_route(query, await store.bus_places())
    if route is None:
        return None
    origin, dest = route
    after = parse_time(query) or (now or datetime.now(BD_TZ)).strftime("%H:%M")
    ferries = await store.next_ferries(origin, dest, after)
    answer = _format_ferries(origin, dest, after, ferries)
    return Retrieval(context=answer, top_score=1.0, direct_answer=answer)


# ---------- tide ----------
def _format_tides(station: str, date: str, events: list[TideEvent]) -> str:
    if not events:
        return f"No tide data for {station} on {date}. Text OP for help."
    parts = [f"{e.event} {e.time}" + (f" ({e.height_m}m)" if e.height_m is not None else "") for e in events]
    return f"{station} tide {date}: " + ", ".join(parts) + "."


async def _tide(store: KnowledgeStore, query: str, now: datetime | None) -> Retrieval | None:
    station = _find_single_place(query, await store.tide_stations())
    if station is None:
        return None
    tokens = set(_norm(query).split())
    when = now or datetime.now(BD_TZ)
    if tokens & TOMORROW_WORDS:
        when = when + timedelta(days=1)
    date = when.strftime("%Y-%m-%d")
    events = await store.tides(station, date)
    answer = _format_tides(station, date, events)
    return Retrieval(context=answer, top_score=1.0, direct_answer=answer)


# ---------- cyclone signal ----------
async def _cyclone(store: KnowledgeStore, query: str) -> Retrieval:
    tokens = set(_norm(query).split())
    m = _SIGNAL_NUM.search(query)
    if not m:
        answer = "Text SIGNAL and a number 1-11 to check a cyclone warning, e.g. SIGNAL 5."
        return Retrieval(context=answer, top_score=1.0, direct_answer=answer)

    code = int(m.group(1))
    authority = "IMD" if tokens & IMD_WORDS else "BMD"
    port_type = "river" if tokens & RIVER_WORDS else "sea"
    sig = await store.cyclone_signal(authority, port_type, code)
    if sig is None:
        answer = f"No {authority} {port_type}-port signal {code} on file. Text OP for help."
        return Retrieval(context=answer, top_score=1.0, direct_answer=answer)

    answer = sig.sms_text if sig.verified else f"(unverified) {sig.sms_text}"
    return Retrieval(context=answer, top_score=1.0, direct_answer=answer)


async def _search(store: KnowledgeStore, query: str) -> Retrieval:
    faqs, guides = await asyncio.gather(store.search_faqs(query, 2), store.search_guides(query, 3))
    terms = query_terms(query)
    rescored = [
        replace(h, score=max(h.score, _coverage(terms, f"{h.title} {h.text}")))
        for h in [*faqs, *guides]
    ]
    hits = sorted(rescored, key=lambda h: h.score, reverse=True)[:4]
    lines: list[str] = []
    used = 0
    for i, h in enumerate(hits, 1):
        line = f"[{i}] {h.title}: {_squash(h.text)[:MAX_SNIPPET_CHARS]}"
        if used + len(line) > MAX_CONTEXT_CHARS:
            break
        lines.append(line)
        used += len(line)
    return Retrieval(
        context="\n".join(lines),
        hits=tuple(hits),
        top_score=hits[0].score if hits else 0.0,
    )


# ---------- entry point ----------
async def retrieve(
    store: KnowledgeStore,
    intent: str,
    query: str,
    phone: str | None = None,
    now: datetime | None = None,
) -> Retrieval:
    if intent == "emergency":
        return await _emergency(store, phone)
    if intent == "operator":
        return Retrieval()
    if intent == "cyclone":
        return await _cyclone(store, query)
    if intent == "transit":
        result = await _transit(store, query, now)
        if result is not None:
            return result
    if intent == "ferry":
        result = await _ferry(store, query, now)
        if result is not None:
            return result
    if intent == "tide":
        result = await _tide(store, query, now)
        if result is not None:
            return result
    return await _search(store, query)