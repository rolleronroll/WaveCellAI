#!/usr/bin/env python3
"""Bangladesh data fetcher for the TravelAI project.

What this script actually does:
  [1] DOWNLOADS maritime boundary geometry from MarineRegions (after checking the record name).
  [2] DOWNLOADS a 7-day marine FORECAST from Open-Meteo (model output, NOT buoy readings).
  [3] WRITES BMD cyclone-signal summaries typed in by hand (paraphrased, partly unverified).
  [4] WRITES a short emergency-number list typed in by hand, compared against official pages.

Sections 3 and 4 are NOT downloads. The manifest and the console say so.
Exit code is 1 if any download failed.
"""

from __future__ import annotations

import json
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
# from src.config import get_settings

BACKEND_DIR = Path(__file__).resolve().parents[1]   # this file lives in backend/scripts/
# _settings = get_settings()
# DATA_DIR = _settings.data_path
# OUTPUT_DIR = _settings.output_path

DATA_DIR = BACKEND_DIR / "data"
OUTPUT_DIR = BACKEND_DIR / "output"
USER_AGENT = "TravelAI-data-fetcher/1.0"

RESULTS: list[dict] = []


# ---------------------------------------------------------------- helpers
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(BACKEND_DIR))
    except ValueError:
        return str(path)


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def backup_if_exists(path: Path) -> Path | None:
    if path.exists():
        bak = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, bak)
        return bak
    return None


def get_json(url: str, timeout: int = 20, retries: int = 2):
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last = exc
            if 400 <= exc.code < 500:  # client errors will not fix themselves
                break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
        if attempt < retries:
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(str(last))


def record(dataset: str, status: str, detail: str, **extra) -> None:
    RESULTS.append({"dataset": dataset, "status": status, "detail": detail, **extra})
    print(f"  [{status}] {dataset}: {detail}")


def describe(data) -> str:
    if isinstance(data, dict):
        return f"object with keys {sorted(data)[:6]}"
    if isinstance(data, list):
        return f"list of {len(data)} items"
    return type(data).__name__


# ------------------------------------------- 1. MarineRegions boundaries
# Uses Marine Regions' WFS service. The URL pattern follows the example on
# marineregions.org/webservices.php; the layer names MarineRegions:eez (EEZ) and
# MarineRegions:eez_12nm (territorial sea) are listed in the service's capabilities.
WFS_URL = "https://geo.vliz.be/geoserver/MarineRegions/wfs"
GIS_ATTRIBUTION = ("Flanders Marine Institute (VLIZ), Marine Regions Maritime Boundaries "
                   "Geodatabase, CC BY 4.0, https://www.marineregions.org/")

GIS_SOURCES = [
    {"file": "bd_eez.json", "layer": "MarineRegions:eez", "mrgid": 8481,
     "label": "Bangladeshi EEZ (200 NM)"},
    {"file": "bd_territorial_sea_12nm.json", "layer": "MarineRegions:eez_12nm", "mrgid": 49195,
     "label": "Bangladeshi territorial sea (12 NM)"},
]


def fetch_gis() -> None:
    for src in GIS_SOURCES:
        title = f"{src['label']} (MRGID {src['mrgid']})"
        params = urllib.parse.urlencode({
            "service": "WFS",
            "version": "1.0.0",
            "request": "GetFeature",
            "typeName": src["layer"],
            "cql_filter": f"mrgid={src['mrgid']}",
            "outputFormat": "application/json",
        })
        url = f"{WFS_URL}?{params}"
        try:
            data = get_json(url, timeout=120)
        except Exception as exc:  # noqa: BLE001
            record(title, "FAILED", f"WFS request failed: {exc}")
            continue

        features = data.get("features") if isinstance(data, dict) else None
        if not features:
            record(title, "FAILED",
                   "WFS returned no features for this MRGID (the layer's id attribute may differ)")
            continue

        props = json.dumps([f.get("properties", {}) for f in features], ensure_ascii=False).lower()
        if "bangladesh" not in props:
            record(title, "FAILED", "features do not mention Bangladesh; NOT saved. Check the MRGID.")
            continue

        out = DATA_DIR / "gis" / src["file"]
        write_json(out, data)  # GeoJSON saved exactly as received
        record(title, "OK", f"{len(features)} feature(s), GeoJSON; saved to {rel(out)}",
               source_url=url, fetched_at=now_iso(), attribution=GIS_ATTRIBUTION)


# ------------------------------------------------ 2. Open-Meteo forecast
MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
MARINE_VARS = ["wave_height", "wave_direction", "swell_wave_height", "ocean_current_velocity"]

# Coordinates are approximate points chosen by the script author. They are NOT
# buoys or official stations.
POINTS = [
    {"label": "Off Cox's Bazar (approx.)", "lat": 21.4295, "lon": 91.9712},
    {"label": "Off Chattogram (approx.)", "lat": 22.2285, "lon": 91.8023},
    {"label": "Near St. Martin's Island", "lat": 20.6230, "lon": 92.3235},
    {"label": "Off Sundarbans coast, south of Mongla (approx.)", "lat": 21.7639, "lon": 89.6083},
]


def fetch_marine() -> None:
    fetched_at = now_iso()
    stations: list[dict] = []
    for pt in POINTS:
        params = urllib.parse.urlencode({
            "latitude": pt["lat"],
            "longitude": pt["lon"],
            "hourly": ",".join(MARINE_VARS),
            "timezone": "Asia/Dhaka",
            "cell_selection": "sea",  # prefer ocean grid cells over land cells
        })
        url = f"{MARINE_URL}?{params}"
        try:
            data = get_json(url)
        except Exception as exc:  # noqa: BLE001
            record(pt["label"], "FAILED", f"request failed: {exc}")
            continue

        hourly = data.get("hourly") or {}
        hours = len(hourly.get("time", []))
        non_null = {v: sum(x is not None for x in hourly.get(v, [])) for v in MARINE_VARS}
        if hours == 0 or not any(non_null.values()):
            record(pt["label"], "FAILED", "no usable values (point may be outside the model grid)")
            continue

        all_null = [v for v, n in non_null.items() if n == 0]
        stations.append({
            "label": pt["label"],
            "requested_point": {"lat": pt["lat"], "lon": pt["lon"]},
            "grid_cell_used": {"lat": data.get("latitude"), "lon": data.get("longitude")},
            "elevation": data.get("elevation"),
            "hourly_units": data.get("hourly_units", {}),
            "hourly": hourly,
            "non_null_counts": non_null,
            "fetched_at": fetched_at,
            "source_url": url,
        })
        record(pt["label"], "PARTIAL" if all_null else "OK",
               f"{hours} hourly rows" + (f"; all-null variables: {all_null}" if all_null else ""))

    if not stations:
        return  # nothing usable, so no file is written; the summary will show FAILED

    out = DATA_DIR / "marine" / "bay_of_bengal_marine_forecast.json"
    write_json(out, {
        "_meta": {
            "data_type": "model forecast (NOT observations, NOT buoy telemetry)",
            "source": "Open-Meteo Marine API",
            "forecast_window": "about 7 days (API default); a one-time snapshot that goes stale",
            "fetched_at": fetched_at,
            "attribution": "Data from Open-Meteo.com (CC BY 4.0); wave forecasts include DWD ICON Wave. "
                           "Attribute Open-Meteo and DWD when republishing.",
        },
        "stations": stations,
    })
    print(f"  saved {len(stations)}/{len(POINTS)} points to {rel(out)}")


# ------------------------------------------------- 3. BMD signals (hand-typed)
BMD_REFERENCES = [
    "https://www.tbsnews.net/bangladesh/environment/what-signals-1-11-mean-maritime-ports-during-storms-860361",
    "https://www.dhakatribune.com/bangladesh/2022/10/24/do-you-know-the-meaning-of-each-marine-signals-1",
    "https://unb.com.bd/category/bangladesh/what-each-cyclone-warning-signal-means/103201",
    "https://en.banglatribune.com/national/news/44157/Signal-codes-for-storm",
]

SEA_PORT_SIGNALS = [
    {"code": 1, "name": "Distant Cautionary", "verified": True,
     "summary": "Squally weather (about 61 km/h) in the distant sea where a storm may form.",
     "sms": "BMD sea signal 1 (Distant Cautionary): squally weather far out at sea, a storm may form."},
    {"code": 2, "name": "Distant Warning", "verified": False,
     "note": "Wording not confirmed against a source.",
     "summary": "A storm has formed in the distant sea.",
     "sms": "BMD sea signal 2 (Distant Warning): a storm has formed far out at sea."},
    {"code": 3, "name": "Local Cautionary", "verified": True,
     "summary": "Port threatened by squally weather, wind 40-50 km/h.",
     "sms": "BMD sea signal 3 (Local Cautionary): port threatened by squalls, winds 40-50 km/h."},
    {"code": 4, "name": "Local Warning", "verified": False,
     "note": "Wind speed not confirmed against a source.",
     "summary": "Port threatened by a storm.",
     "sms": "BMD sea signal 4 (Local Warning): port threatened by a storm."},
    {"code": 5, "name": "Danger", "verified": True,
     "summary": "Slight or moderate storm (62-88 km/h) expected to cross the coast south of "
                "Chattogram or Cox's Bazar port and east of Mongla port.",
     "sms": "BMD sea signal 5 (Danger): storm of 62-88 km/h expected to cross coast south of "
            "Chattogram/Cox's Bazar, east of Mongla."},
    {"code": 6, "name": "Danger", "verified": True,
     "summary": "Slight or moderate storm (62-88 km/h) expected to cross the coast north of "
                "Chattogram or Cox's Bazar port and west of Mongla port.",
     "sms": "BMD sea signal 6 (Danger): storm of 62-88 km/h expected to cross coast north of "
            "Chattogram/Cox's Bazar, west of Mongla."},
    {"code": 7, "name": "Danger", "verified": False,
     "note": "Inferred from the south/north/over-or-near pattern; not confirmed for this number.",
     "summary": "Slight or moderate storm (62-88 km/h) expected over or near the port.",
     "sms": "BMD sea signal 7 (Danger): storm of 62-88 km/h expected over or near the port."},
    {"code": 8, "name": "Great Danger", "verified": True,
     "summary": "Great-intensity storm (89 km/h or more) expected to cross the coast south of "
                "Chattogram or Cox's Bazar port and east of Mongla port.",
     "sms": "BMD sea signal 8 (Great Danger): storm of 89+ km/h expected to cross coast south of "
            "Chattogram/Cox's Bazar, east of Mongla."},
    {"code": 9, "name": "Great Danger", "verified": False,
     "note": "Inferred from the group pattern; one source words this signal differently.",
     "summary": "Great-intensity storm (89 km/h or more) expected to cross the coast north of "
                "Chattogram or Cox's Bazar port and west of Mongla port.",
     "sms": "BMD sea signal 9 (Great Danger): storm of 89+ km/h expected to cross coast north of "
            "Chattogram/Cox's Bazar, west of Mongla."},
    {"code": 10, "name": "Great Danger", "verified": True,
     "summary": "Great-intensity storm (89 km/h or more) expected over or near the port.",
     "sms": "BMD sea signal 10 (Great Danger): storm of 89+ km/h expected over or near the port."},
    {"code": 11, "name": "Failure of Communication", "verified": True,
     "summary": "Communication with the meteorological warning centre has broken down and the "
                "local officer considers there is danger of bad weather.",
     "sms": "BMD sea signal 11: contact with the storm warning centre is lost and the local "
            "officer sees danger of bad weather."},
]


def write_bmd_signals() -> None:
    for s in SEA_PORT_SIGNALS:  # SMS texts must fit one GSM-7 segment
        if len(s["sms"]) > 160 or not s["sms"].isascii():
            raise ValueError(f"signal {s['code']}: SMS text is too long or not plain ASCII")

    out = DATA_DIR / "weather" / "bmd_signals_paraphrased.json"
    write_json(out, {
        "_meta": {
            "kind": "paraphrased by hand, NOT downloaded, NOT verbatim",
            "primary_source_checked": False,
            "secondary_references": BMD_REFERENCES,
            "unverified_codes": [s["code"] for s in SEA_PORT_SIGNALS if not s["verified"]],
            "group_note": "Higher numbers within the danger and great-danger groups show where "
                          "the storm is expected to cross, not how intense it is.",
            "advice_policy": "No evacuation or safety advice is included. It is not part of "
                             "the signal definitions.",
            "review_required": "Have BMD or a qualified Bangladeshi maritime authority confirm "
                               "all wording before real users rely on it.",
        },
        "sea_ports": SEA_PORT_SIGNALS,
        "river_ports": [],
        "river_ports_note": "Not loaded on purpose: the wording was not verified. Copy the 4 river "
                            "signals from the BMD site and add them here.",
    })
    record("BMD cyclone signals", "HAND-TYPED",
           f"{len(SEA_PORT_SIGNALS)} sea-port signals saved to {rel(out)}; "
           f"unverified: {[s['code'] for s in SEA_PORT_SIGNALS if not s['verified']]}; river ports empty")


# ------------------------------------------ 4. Emergency numbers (hand-typed)
BD_PORTAL = "https://bangladesh.gov.bd/pages/static-pages/69a55ba386514399668e4e89"
BCG_PAGE = "https://coastguard.gov.bd/pages/office-heads/6922d89ddbfbab28ce045c47"
CHECKED_ON = "2026-10-04"


def _contact(service: str, number: str, notes: str, source_url: str) -> dict:
    return {
        "country": "Bangladesh",
        "service": service,        # short on purpose: it goes straight into an SMS
        "number": number,
        "notes": notes,
        "source_url": source_url,
        "checked_on": CHECKED_ON,
        "check_method": "compared with official government page text; NOT test-dialed",
    }


def write_emergency() -> None:
    rows = [
        _contact("Police/Fire/Ambulance", "999", "National emergency number.", BD_PORTAL),
        _contact("Coast Guard", "16111",
                 "Coast, coastal areas, sea areas and waterways. Callable from all mobile operators.",
                 BCG_PAGE),
        _contact("Coast Guard, ship sat phone", "+8809610916111",
                 "For commercial ships calling by satellite phone.", BCG_PAGE),
    ]
    path = OUTPUT_DIR / "emergency_contacts.json"   # the file build_knowledge_db reads
    bak = backup_if_exists(path)
    write_json(path, rows)
    record("Emergency contacts", "HAND-TYPED",
           f"{len(rows)} numbers saved to {rel(path)}"
           + (f" (previous file backed up to {rel(bak)})" if bak else ""))
    print("  REMINDER: confirm 16111 with the Coast Guard before real users depend on it.")


# --------------------------------------------------------------------- main
def main() -> int:
    print("=" * 60)
    print(" Bangladesh data fetcher: 2 downloads + 2 hand-typed datasets")
    print("=" * 60)

    steps = [
        ("[1/4] MarineRegions boundaries (download)", fetch_gis),
        ("[2/4] Open-Meteo marine FORECAST (download)", fetch_marine),
        ("[3/4] BMD cyclone signals (hand-typed, paraphrased)", write_bmd_signals),
        ("[4/4] Emergency numbers (hand-typed, checked against official pages)", write_emergency),
    ]
    for title, fn in steps:
        print(f"\n{title}")
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            record(title, "FAILED", f"unexpected error: {exc}")

    write_json(DATA_DIR / "manifest.json", {"generated_at": now_iso(), "results": RESULTS})

    counts: dict[str, int] = {}
    for r in RESULTS:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print("\n" + "=" * 60)
    print(" Downloaded OK: {} | Partial: {} | Failed: {} | Hand-typed (not downloaded): {}".format(
        counts.get("OK", 0), counts.get("PARTIAL", 0), counts.get("FAILED", 0), counts.get("HAND-TYPED", 0)))
    for r in RESULTS:
        if r["status"] in ("FAILED", "PARTIAL"):
            print(f"   {r['status']}: {r['dataset']} -> {r['detail']}")
    print(f" Manifest: {rel(DATA_DIR / 'manifest.json')}")
    print(" Hand-typed datasets need human review before real use.")

    if counts.get("FAILED"):
        print("\n SOME STEPS FAILED. Do not treat the data as complete.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())