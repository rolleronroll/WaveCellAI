#!/usr/bin/env python3
"""Fetch EEZ boundaries for a configurable list of countries, one WFS call per country.

Before filtering, this asks the WFS service (DescribeFeatureType) which attribute
names actually exist on the EEZ layer, instead of guessing a field name blind. It
then builds a cql_filter using whichever of a few known candidate field names is
present, and verifies the country's name appears in the result before saving.

Usage (from the backend folder, or by running this file directly):
    uv run python -m scripts.fetch_gis_data
    uv run python scripts/fetch_gis_data.py
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# Make `src` importable whether this runs as `-m scripts.fetch_gis_data` (cwd=backend)
# or as a direct script path (`python scripts/fetch_gis_data.py` from anywhere).
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# from src.config import get_settings  # noqa: E402

DATA_DIR = BACKEND_DIR / "data"
OUTPUT_DIR = BACKEND_DIR / "output"


USER_AGENT = "TravelAI-data-fetcher/1.0"
WFS_URL = "https://geo.vliz.be/geoserver/MarineRegions/wfs"
LAYER = "MarineRegions:eez"
ATTRIBUTION = ("Flanders Marine Institute (VLIZ), Marine Regions Maritime Boundaries "
               "Geodatabase, CC BY 4.0, https://www.marineregions.org/")

# Checked in this order; the first one the live schema actually has gets used.
CANDIDATE_FIELDS = ["territory1", "geoname", "sovereign1", "union"]

COUNTRIES = [
    "Bangladesh", "India", "Pakistan", "Sri Lanka", "Myanmar", "Maldives",
    "Philippines", "Vietnam", "Indonesia", "Thailand", "Cambodia", "Madagascar", "Mozambique",
    "Fiji", "Vanuatu", "Tonga", "Kiribati", "Tuvalu", "Solomon Islands",
    "Haiti", "Jamaica", "Dominican Republic", "Cuba", "Bahamas",
]

RESULTS: list[dict] = []


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slug(name: str) -> str:
    return name.lower().replace(" ", "_").replace("'", "")


def get_bytes(url: str, timeout: int = 60, retries: int = 2) -> bytes:
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            last = exc
            if 400 <= exc.code < 500:
                break
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
        if attempt < retries:
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(str(last))


def get_json(url: str, timeout: int = 60, retries: int = 2):
    raw = get_bytes(url, timeout, retries)
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"response was not JSON: {exc}") from exc


def record(dataset: str, status: str, detail: str, **extra) -> None:
    RESULTS.append({"dataset": dataset, "status": status, "detail": detail, **extra})
    print(f"  [{status}] {dataset}: {detail}")


def discover_filter_field() -> str | None:
    """Ask the service which attribute names exist on the EEZ layer, via
    DescribeFeatureType, and return the first candidate that's actually present."""
    params = urllib.parse.urlencode({
        "service": "WFS", "version": "1.0.0", "request": "DescribeFeatureType", "typeName": LAYER,
    })
    url = f"{WFS_URL}?{params}"
    try:
        xml = get_bytes(url, timeout=30).decode("utf-8", errors="ignore")
    except Exception as exc:  # noqa: BLE001
        record("schema discovery", "FAILED", f"DescribeFeatureType failed: {exc}")
        return None

    names = set(re.findall(r'name="([a-zA-Z0-9_]+)"', xml))
    names_lower = {n.lower(): n for n in names}
    for candidate in CANDIDATE_FIELDS:
        if candidate in names_lower:
            record("schema discovery", "OK", f"using field '{names_lower[candidate]}' (found on the live layer)")
            return names_lower[candidate]

    record("schema discovery", "FAILED",
           f"none of {CANDIDATE_FIELDS} found on the layer; available fields: {sorted(names)[:20]}")
    return None


def fetch_country(country: str, field: str, data_dir: Path) -> None:
    safe_value = country.replace("'", "''")  # escape for CQL string literal
    params = urllib.parse.urlencode({
        "service": "WFS", "version": "1.0.0", "request": "GetFeature", "typeName": LAYER,
        "cql_filter": f"{field} ILIKE '%{safe_value}%'",
        "outputFormat": "application/json",
    })
    url = f"{WFS_URL}?{params}"
    try:
        data = get_json(url, timeout=60)
    except Exception as exc:  # noqa: BLE001
        record(country, "FAILED", f"WFS request failed: {exc}")
        return

    features = data.get("features") if isinstance(data, dict) else None
    if not features:
        record(country, "FAILED", f"no features matched {field} ILIKE '%{country}%'")
        return

    props_text = json.dumps([f.get("properties", {}) for f in features], ensure_ascii=False).lower()
    if country.lower() not in props_text:
        record(country, "FAILED", "matched features but country name not confirmed in properties; NOT saved")
        return

    out = data_dir / "gis" / f"eez_{slug(country)}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    record(country, "OK", f"{len(features)} feature(s) saved to {out.relative_to(data_dir.parent)}",
           source_url=url, fetched_at=now_iso(), attribution=ATTRIBUTION)


def main() -> int:
    # settings = get_settings()
    data_dir = DATA_DIR
    print(f"Backend dir: {BACKEND_DIR}")
    print(f"Fetching EEZ boundaries for {len(COUNTRIES)} countries -> {data_dir / 'gis'}\n")

    field = discover_filter_field()
    if field is None:
        print("\nCould not confirm a usable filter field; stopping before per-country calls.")
        manifest = data_dir / "gis_manifest.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({"generated_at": now_iso(), "results": RESULTS}, indent=2), encoding="utf-8")
        return 1

    for country in COUNTRIES:
        fetch_country(country, field, data_dir)
        time.sleep(0.5)  # be polite to the free service

    manifest = data_dir / "gis_manifest.json"
    manifest.write_text(
        json.dumps({"generated_at": now_iso(), "field_used": field, "countries": COUNTRIES, "results": RESULTS},
                   indent=2),
        encoding="utf-8",
    )

    counts: dict[str, int] = {}
    for r in RESULTS:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print("\n" + "=" * 60)
    print(f" OK: {counts.get('OK', 0)} | Failed: {counts.get('FAILED', 0)} of {len(COUNTRIES)}")
    for r in RESULTS:
        if r["status"] != "OK":
            print(f"   {r['status']}: {r['dataset']} -> {r['detail']}")
    print(f" Manifest: {manifest}")

    return 1 if counts.get("FAILED") else 0


if __name__ == "__main__":
    sys.exit(main())