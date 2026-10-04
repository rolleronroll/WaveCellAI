"""Read-only SQLite knowledge base: FTS5 search + structured lookups."""

from __future__ import annotations

import asyncio
import re
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE guide_snippets (
    id INTEGER PRIMARY KEY,
    place TEXT NOT NULL,
    section TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL,
    source_url TEXT NOT NULL DEFAULT ''
);
CREATE VIRTUAL TABLE guide_fts USING fts5(
    place, section, text,
    content='guide_snippets', content_rowid='id',
    tokenize='porter unicode61 remove_diacritics 2'
);

CREATE TABLE faqs (
    id INTEGER PRIMARY KEY,
    category TEXT NOT NULL DEFAULT '',
    question TEXT NOT NULL,
    answer TEXT NOT NULL
);
CREATE VIRTUAL TABLE faq_fts USING fts5(
    question, answer,
    content='faqs', content_rowid='id',
    tokenize='porter unicode61 remove_diacritics 2'
);

CREATE TABLE emergency_contacts (
    id INTEGER PRIMARY KEY,
    country TEXT NOT NULL,
    service TEXT NOT NULL,
    number TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE bus_schedules (
    id INTEGER PRIMARY KEY,
    route TEXT NOT NULL,
    origin TEXT NOT NULL COLLATE NOCASE,
    destination TEXT NOT NULL COLLATE NOCASE,
    departs TEXT NOT NULL,           -- 'HH:MM' 24h, sortable as text
    days TEXT NOT NULL DEFAULT 'daily',
    fare TEXT,
    duration_min INTEGER
);
CREATE INDEX idx_bus_route ON bus_schedules(origin, destination, departs);

CREATE TABLE ferry_schedules (
    id INTEGER PRIMARY KEY,
    operator TEXT NOT NULL DEFAULT '',   -- BIWTC / BIWTA / private
    route TEXT NOT NULL,
    vessel_type TEXT NOT NULL DEFAULT '',  -- ferry / launch / speedboat
    origin TEXT NOT NULL COLLATE NOCASE,
    destination TEXT NOT NULL COLLATE NOCASE,
    departs TEXT NOT NULL,
    days TEXT NOT NULL DEFAULT 'daily',
    fare TEXT,
    duration_min INTEGER
);
CREATE INDEX idx_ferry_route ON ferry_schedules(origin, destination, departs);

CREATE TABLE tide_tables (
    id INTEGER PRIMARY KEY,
    station TEXT NOT NULL COLLATE NOCASE,
    date TEXT NOT NULL,         -- 'YYYY-MM-DD'
    event TEXT NOT NULL,        -- 'high' | 'low'
    time TEXT NOT NULL,         -- 'HH:MM'
    height_m REAL
);
CREATE INDEX idx_tide_station_date ON tide_tables(station, date);

CREATE TABLE cyclone_signals (
    id INTEGER PRIMARY KEY,
    authority TEXT NOT NULL,     -- 'BMD' | 'IMD'
    port_type TEXT NOT NULL,     -- 'sea' | 'river'
    code INTEGER NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL,
    sms_text TEXT NOT NULL,
    verified INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_signal_authority_code ON cyclone_signals(authority, port_type, code);




"""

_TOKEN = re.compile(r"\w+", re.UNICODE)
_STOP = frozenset(
    "the a an is are was to of in on at for and or i me my you your do does how what where "
    "when which can could please tell show want need get".split()
)

#
# def build_match(query: str, max_terms: int = 12) -> str:
#     """Turn free text into a safe FTS5 query: quoted tokens joined by OR."""
#     terms: list[str] = []
#     for tok in _TOKEN.findall(query.lower()):
#         if len(tok) > 1 and tok not in _STOP and tok not in terms:
#             terms.append(tok)
#     return " OR ".join(f'"{t}"' for t in terms[:max_terms])


def query_terms(query: str, max_terms: int = 12) -> list[str]:
    terms: list[str] = []
    for tok in _TOKEN.findall(query.lower()):
        if len(tok) > 1 and tok not in _STOP and tok not in terms:
            terms.append(tok)
    return terms[:max_terms]


def build_match(query: str, max_terms: int = 12) -> str:
    """Turn free text into a safe FTS5 query: quoted tokens joined by OR."""
    return " OR ".join(f'"{t}"' for t in query_terms(query, max_terms))


def _score(rank: float) -> float:
    """SQLite's bm25() is negative (more negative = better). Map to 0..1.

    This is a heuristic for the confidence scorer, not a calibrated probability.
    """
    raw = -rank
    return raw / (raw + 4.0) if raw > 0 else 0.0


@dataclass(frozen=True)
class Hit:
    text: str
    source: str  # "guide" | "faq"
    title: str  # place name or FAQ question
    score: float  # 0..1
    url: str = ""


@dataclass(frozen=True)
class BusDeparture:
    route: str
    origin: str
    destination: str
    departs: str
    days: str
    fare: str | None
    duration_min: int | None
    tomorrow: bool = False


@dataclass(frozen=True)
class FerryDeparture:
    operator: str
    route: str
    vessel_type: str
    origin: str
    destination: str
    departs: str
    days: str
    fare: str | None
    duration_min: int | None
    tomorrow: bool = False


@dataclass(frozen=True)
class TideEvent:
    station: str
    date: str
    event: str
    time: str
    height_m: float | None


@dataclass(frozen=True)
class CycloneSignal:
    authority: str
    port_type: str
    code: int
    name: str
    summary: str
    sms_text: str
    verified: bool


@dataclass(frozen=True)
class EmergencyContact:
    country: str
    service: str
    number: str
    notes: str


class KnowledgeStore:
    def __init__(self, path: str | Path) -> None:
        p = Path(path).resolve()
        if not p.exists():
            raise FileNotFoundError(
                f"Knowledge DB not found at {p}. Run: uv run python -m scripts.build_knowledge_db --seed"
            )
        # Read-only: safe to ship inside a deploy image; as_uri() handles Windows paths.
        self._conn = sqlite3.connect(f"{p.as_uri()}?mode=ro", uri=True, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._places: list[str] | None = None

    # ---------- sync core ----------
    def _query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def search_guides_sync(self, query: str, limit: int = 3) -> list[Hit]:
        match = build_match(query)
        if not match:
            return []
        rows = self._query(
            """
            SELECT g.place, g.section, g.text, g.source_url,
                   bm25(guide_fts, 4.0, 1.0, 1.0) AS rank
            FROM guide_fts JOIN guide_snippets g ON g.id = guide_fts.rowid
            WHERE guide_fts MATCH ? ORDER BY rank LIMIT ?
            """,
            (match, limit),
        )
        return [
            Hit(r["text"], "guide", f'{r["place"]} {r["section"]}'.strip(), _score(r["rank"]), r["source_url"])
            for r in rows
        ]

    def search_faqs_sync(self, query: str, limit: int = 3) -> list[Hit]:
        match = build_match(query)
        if not match:
            return []
        rows = self._query(
            """
            SELECT f.question, f.answer, bm25(faq_fts, 3.0, 1.0) AS rank
            FROM faq_fts JOIN faqs f ON f.id = faq_fts.rowid
            WHERE faq_fts MATCH ? ORDER BY rank LIMIT ?
            """,
            (match, limit),
        )
        return [Hit(r["answer"], "faq", r["question"], _score(r["rank"])) for r in rows]

    def emergency_sync(self, country: str | None = None) -> list[EmergencyContact]:
        if country:
            rows = self._query(
                "SELECT * FROM emergency_contacts WHERE country = ? COLLATE NOCASE", (country,)
            )
        else:
            rows = self._query("SELECT * FROM emergency_contacts")
        return [EmergencyContact(r["country"], r["service"], r["number"], r["notes"]) for r in rows]

    def next_buses_sync(
            self, origin: str, destination: str, after: str = "00:00", limit: int = 3
    ) -> list[BusDeparture]:
        base = (
            "SELECT route, origin, destination, departs, days, fare, duration_min "
            "FROM bus_schedules WHERE origin = ? AND destination = ? "
        )
        rows = self._query(base + "AND departs >= ? ORDER BY departs LIMIT ?", (origin, destination, after, limit))
        tomorrow = False
        if not rows:  # nothing left today: show the earliest departures tomorrow
            rows = self._query(base + "ORDER BY departs LIMIT ?", (origin, destination, limit))
            tomorrow = True
        return [
            BusDeparture(r["route"], r["origin"], r["destination"], r["departs"],
                         r["days"], r["fare"], r["duration_min"], tomorrow)
            for r in rows
        ]

    def next_ferries_sync(
        self, origin: str, destination: str, after: str = "00:00", limit: int = 3
    ) -> list[FerryDeparture]:
        base = (
            "SELECT operator, route, vessel_type, origin, destination, departs, days, fare, duration_min "
            "FROM ferry_schedules WHERE origin = ? AND destination = ? "
        )
        rows = self._query(base + "AND departs >= ? ORDER BY departs LIMIT ?", (origin, destination, after, limit))
        tomorrow = False
        if not rows:
            rows = self._query(base + "ORDER BY departs LIMIT ?", (origin, destination, limit))
            tomorrow = True
        return [
            FerryDeparture(r["operator"], r["route"], r["vessel_type"], r["origin"], r["destination"],
                            r["departs"], r["days"], r["fare"], r["duration_min"], tomorrow)
            for r in rows
        ]

    def tide_stations_sync(self) -> list[str]:
        rows = self._query("SELECT DISTINCT station FROM tide_tables")
        return sorted(r["station"] for r in rows)

    def tides_sync(self, station: str, date: str) -> list[TideEvent]:
        rows = self._query(
            "SELECT station, date, event, time, height_m FROM tide_tables "
            "WHERE station = ? COLLATE NOCASE AND date = ? ORDER BY time",
            (station, date),
        )
        return [TideEvent(r["station"], r["date"], r["event"], r["time"], r["height_m"]) for r in rows]

    def cyclone_signal_sync(self, authority: str, port_type: str, code: int) -> CycloneSignal | None:
        rows = self._query(
            "SELECT * FROM cyclone_signals WHERE authority = ? AND port_type = ? AND code = ?",
            (authority, port_type, code),
        )
        if not rows:
            return None
        r = rows[0]
        return CycloneSignal(r["authority"], r["port_type"], r["code"], r["name"],
                              r["summary"], r["sms_text"], bool(r["verified"]))

    def bus_places_sync(self) -> list[str]:
        if self._places is None:
            rows = self._query(
                "SELECT origin AS p FROM bus_schedules UNION SELECT destination FROM bus_schedules "
                "UNION SELECT origin FROM ferry_schedules UNION SELECT destination FROM ferry_schedules"
            )
            self._places = sorted(r["p"] for r in rows)
        return self._places

    # ---------- async wrappers (don't block the event loop) ----------
    async def search_guides(self, query: str, limit: int = 3) -> list[Hit]:
        return await asyncio.to_thread(self.search_guides_sync, query, limit)

    async def search_faqs(self, query: str, limit: int = 3) -> list[Hit]:
        return await asyncio.to_thread(self.search_faqs_sync, query, limit)

    async def emergency(self, country: str | None = None) -> list[EmergencyContact]:
        return await asyncio.to_thread(self.emergency_sync, country)

    async def next_buses(
            self, origin: str, destination: str, after: str = "00:00", limit: int = 3
    ) -> list[BusDeparture]:
        return await asyncio.to_thread(self.next_buses_sync, origin, destination, after, limit)

    async def next_ferries(self, origin: str, destination: str, after: str = "00:00", limit: int = 3) -> list[FerryDeparture]:
        return await asyncio.to_thread(self.next_ferries_sync, origin, destination, after, limit)

    async def tide_stations(self) -> list[str]:
        return await asyncio.to_thread(self.tide_stations_sync)

    async def tides(self, station: str, date: str) -> list[TideEvent]:
        return await asyncio.to_thread(self.tides_sync, station, date)

    async def cyclone_signal(self, authority: str, port_type: str, code: int) -> CycloneSignal | None:
        return await asyncio.to_thread(self.cyclone_signal_sync, authority, port_type, code)

    async def bus_places(self) -> list[str]:
        return await asyncio.to_thread(self.bus_places_sync)

    def close(self) -> None:
        self._conn.close()
