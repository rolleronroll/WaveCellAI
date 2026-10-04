"""Build the read-only SQLite knowledge base.

Usage (from the backend folder):
    uv run python -m scripts.build_knowledge_db --seed     # sample data only
    uv run python -m scripts.build_knowledge_db            # load real data files

Expected input files (JSON; a missing file is skipped, not an error):
    data/wikivoyage_snippets/*.json   [{place, section, text, url}]
    data/faqs.json                    [{category, question, answer}]
    data/waterways/*.json             [{operator, route, vessel_type, origin,
                                          destination, departs, days, fare, duration_min}]
    data/tides/*.json                 [{station, date, event, time, height_m}]
    data/weather/*.json               [{authority, port_type, code, name, summary,
                                          sms_text, verified}]
    output/emergency_contacts.json    [{country, service, number, notes}]
    output/gtfs_bus_schedules.json    [{route, origin, destination, departs, days,
                                          fare, duration_min}]

Not loaded here on purpose:
    data/gis/*                        map/coverage data, not text lookups
    AI4Bharat / Samanantar corpus      transliteration training data, not SMS content
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from src.config import get_settings
from src.rag.sqlite_store import SCHEMA_SQL

SEED = {
    "guides": [
        {"place": "Dhaka", "section": "Get around",
         "text": "Rickshaws and CNG auto-rickshaws are common. Agree on the fare before you ride.",
         "url": "seed"},
        {"place": "Cox's Bazar", "section": "See",
         "text": "Long sandy beach on the Bay of Bengal. Sunrise and sunset are the best times to visit.",
         "url": "seed"},
    ],
    "faqs": [
        {"category": "money", "question": "Where can I exchange money?",
         "answer": "Use licensed banks or authorised money changers. Keep your receipt."},
    ],
    "emergency": [
        {"country": "Bangladesh", "service": "National emergency", "number": "999",
         "notes": "Police, fire, ambulance"},
        {"country": "Bangladesh", "service": "Coast Guard", "number": "16111",
         "notes": "Coast, waterways and sea areas"},
    ],
    "buses": [
        {"route": "SAMPLE-1", "origin": "Dhaka", "destination": "Cox's Bazar",
         "departs": "07:30", "days": "daily", "fare": "1200 BDT", "duration_min": 570},
        {"route": "SAMPLE-1", "origin": "Dhaka", "destination": "Cox's Bazar",
         "departs": "21:00", "days": "daily", "fare": "1200 BDT", "duration_min": 570},
    ],
    "ferries": [
        {"operator": "BIWTC", "route": "SAMPLE-F1", "vessel_type": "launch",
         "origin": "Dhaka", "destination": "Barisal", "departs": "20:30",
         "days": "daily", "fare": "400 BDT", "duration_min": 480},
    ],
    "tides": [
        {"station": "Cox's Bazar", "date": "2026-10-04", "event": "high", "time": "06:10", "height_m": 2.1},
        {"station": "Cox's Bazar", "date": "2026-10-04", "event": "low", "time": "12:30", "height_m": 0.6},
    ],
    "signals": [
        {"authority": "BMD", "port_type": "sea", "code": 11, "name": "Failure of Communication",
         "summary": "Communication with the met warning centre has broken down; local officer "
                     "sees danger of bad weather.",
         "sms_text": "BMD sea signal 11: contact with storm warning centre is lost, local officer "
                     "sees danger of bad weather.",
         "verified": 1},
    ],
}


def _load_one(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"  SKIP (bad JSON): {path} ({exc})")
        return []
    if not isinstance(data, list):
        print(f"  SKIP (expected a JSON array): {path}")
        return []
    print(f"  loaded {len(data):>5} rows: {path}")
    return data


def _load_folder(folder: Path) -> list[dict]:
    if not folder.exists():
        print(f"  skip (not found): {folder}")
        return []
    rows = [row for f in sorted(folder.glob("*.json")) for row in _load_one(f)]
    return rows


def _load_bmd_signals(folder: Path) -> list[dict]:
    """bmd_signals_paraphrased.json is a dict with 'sea_ports' / 'river_ports' keys
    (see fetch_real_data.py's write_bmd_signals), not a flat array like the other
    weather files. Flatten it into cyclone_signals rows here."""
    path = folder / "bmd_signals_paraphrased.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"  SKIP (bad JSON): {path} ({exc})")
        return []
    if not isinstance(data, dict):
        print(f"  SKIP (expected an object with sea_ports/river_ports): {path}")
        return []

    rows: list[dict] = []
    for port_type in ("sea_ports", "river_ports"):
        for s in data.get(port_type, []):
            rows.append({
                "authority": "BMD",
                "port_type": "sea" if port_type == "sea_ports" else "river",
                "code": s["code"],
                "name": s.get("name", ""),
                "summary": s.get("summary", ""),
                "sms_text": s.get("sms", s.get("sms_text", "")),
                "verified": 1 if s.get("verified") else 0,
            })
    print(f"  loaded {len(rows):>5} rows: {path} (sea_ports + river_ports)")
    return rows


def build(seed: bool) -> Path:
    s = get_settings()
    out = s.sqlite_file
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    if seed:
        guides, faqs, emergency, buses, ferries, tides, signals = (
            SEED["guides"], SEED["faqs"], SEED["emergency"], SEED["buses"],
            SEED["ferries"], SEED["tides"], SEED["signals"],
        )
    else:
        data_dir, out_dir = Path(s.data_dir), Path(s.output_dir)
        print("Reading source files:")
        guides = _load_folder(data_dir / "wikivoyage_snippets")
        faqs = _load_one(data_dir / "faqs.json")
        emergency = _load_one(out_dir / "emergency_contacts.json")
        buses = _load_one(out_dir / "gtfs_bus_schedules.json")
        ferries = _load_folder(data_dir / "waterways")
        tides = _load_folder(data_dir / "tides")
        # signals = _load_folder(data_dir / "weather")
        signals = _load_bmd_signals(data_dir / "weather")

    con = sqlite3.connect(out)
    try:
        con.executescript(SCHEMA_SQL)

        con.executemany(
            "INSERT INTO guide_snippets(place, section, text, source_url) VALUES (?,?,?,?)",
            [(g["place"], g.get("section", ""), g["text"], g.get("url", "")) for g in guides],
        )
        con.executemany(
            "INSERT INTO faqs(category, question, answer) VALUES (?,?,?)",
            [(f.get("category", ""), f["question"], f["answer"]) for f in faqs],
        )
        con.executemany(
            "INSERT INTO emergency_contacts(country, service, number, notes) VALUES (?,?,?,?)",
            [(e["country"], e["service"], e["number"], e.get("notes", "")) for e in emergency],
        )
        con.executemany(
            "INSERT INTO bus_schedules(route, origin, destination, departs, days, fare, duration_min) "
            "VALUES (?,?,?,?,?,?,?)",
            [(b["route"], b["origin"], b["destination"], b["departs"],
              b.get("days", "daily"), b.get("fare"), b.get("duration_min")) for b in buses],
        )
        con.executemany(
            "INSERT INTO ferry_schedules(operator, route, vessel_type, origin, destination, "
            "departs, days, fare, duration_min) VALUES (?,?,?,?,?,?,?,?,?)",
            [(f.get("operator", ""), f["route"], f.get("vessel_type", ""), f["origin"],
              f["destination"], f["departs"], f.get("days", "daily"), f.get("fare"),
              f.get("duration_min")) for f in ferries],
        )
        con.executemany(
            "INSERT INTO tide_tables(station, date, event, time, height_m) VALUES (?,?,?,?,?)",
            [(t["station"], t["date"], t["event"], t["time"], t.get("height_m")) for t in tides],
        )
        con.executemany(
            "INSERT INTO cyclone_signals(authority, port_type, code, name, summary, sms_text, verified) "
            "VALUES (?,?,?,?,?,?,?)",
            [(sig["authority"], sig["port_type"], sig["code"], sig.get("name", ""),
              sig["summary"], sig["sms_text"], int(sig.get("verified", 0))) for sig in signals],
        )

        con.execute("INSERT INTO guide_fts(guide_fts) VALUES('rebuild')")
        con.execute("INSERT INTO faq_fts(faq_fts) VALUES('rebuild')")
        con.execute("PRAGMA optimize")
        con.commit()
    finally:
        con.close()

    print(
        f"\nBuilt {out}\n"
        f"  guides={len(guides)} faqs={len(faqs)} emergency={len(emergency)} "
        f"buses={len(buses)} ferries={len(ferries)} tides={len(tides)} signals={len(signals)}"
    )
    unverified = [s["code"] for s in signals if not s.get("verified")]
    if unverified:
        print(f"  WARNING: unverified cyclone signal codes: {unverified}. Confirm against BMD/IMD before use.")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true", help="use built-in sample data")
    args = ap.parse_args()
    try:
        build(args.seed)
    except KeyError as exc:
        sys.exit(f"Input row is missing field {exc}. Check the expected formats in this file's docstring.")