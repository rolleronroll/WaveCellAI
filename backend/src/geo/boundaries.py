"""Loads EEZ GeoJSON files (data/gis/eez_*.json) and answers 'which country's waters contain this point'.
Uses bounding boxes so a global set of countries stays fast. Loaded once per process."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from .point_in_polygon import Polygon, distance_to_multipolygon_km, point_in_polygon

log = logging.getLogger(__name__)

NEAR_BORDER_KM = 5.0
PAD_DEG = 1.0   # only countries within about 110 km are checked in detail


def _rings(geom: dict) -> list[Polygon]:
    t, c = geom.get("type"), geom.get("coordinates")
    if t == "Polygon":
        return [[[tuple(pt[:2]) for pt in ring] for ring in c]]
    if t == "MultiPolygon":
        return [[[tuple(pt[:2]) for pt in ring] for ring in poly] for poly in c]
    return []


def _bbox(poly: Polygon) -> tuple[float, float, float, float]:
    xs = [p[0] for p in poly[0]]
    ys = [p[1] for p in poly[0]]
    return min(xs), min(ys), max(xs), max(ys)


@dataclass(frozen=True)
class CountryBoundary:
    country: str
    polygons: list[Polygon]
    bboxes: list[tuple[float, float, float, float]]


@dataclass(frozen=True)
class PositionResult:
    inside_countries: list[str]
    nearest_country: str | None
    nearest_km: float | None
    near_border: bool
    has_data: bool
    complete: bool          # True only if the global EEZ download finished


class BoundaryRegistry:
    def __init__(self, gis_dir: Path) -> None:
        self.countries: dict[str, CountryBoundary] = {}
        self.complete = False
        if not gis_dir.exists():
            log.warning("GIS folder not found at %s; position checks disabled", gis_dir)
            return
        manifest = gis_dir.parent / "gis_manifest_global.json"
        if manifest.exists():
            try:
                self.complete = bool(json.loads(manifest.read_text(encoding="utf-8")).get("complete"))
            except json.JSONDecodeError:
                pass
        for path in sorted(gis_dir.glob("eez_*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                log.warning("Skipping unreadable GIS file %s: %s", path, exc)
                continue
            polys = [r for f in data.get("features", []) for r in _rings(f.get("geometry") or {})]
            if polys:
                name = path.stem.removeprefix("eez_").replace("_", " ").title()
                self.countries[name] = CountryBoundary(name, polys, [_bbox(p) for p in polys])
        log.info("Loaded EEZ boundaries for %d countries (complete=%s)", len(self.countries), self.complete)

    def locate(self, lon: float, lat: float) -> PositionResult:
        inside: list[str] = []
        nearest_country: str | None = None
        nearest_km = float("inf")
        for name, b in self.countries.items():
            near = [p for p, bb in zip(b.polygons, b.bboxes)
                    if bb[0] - PAD_DEG <= lon <= bb[2] + PAD_DEG and bb[1] - PAD_DEG <= lat <= bb[3] + PAD_DEG]
            if not near:
                continue
            if any(point_in_polygon(lon, lat, p) for p in near):
                inside.append(name)
            d = distance_to_multipolygon_km(lon, lat, near)
            if d < nearest_km:
                nearest_km, nearest_country = d, name
        found = nearest_country is not None
        return PositionResult(inside, nearest_country, round(nearest_km, 1) if found else None,
                              found and nearest_km <= NEAR_BORDER_KM, bool(self.countries), self.complete)


def format_position_reply(result: PositionResult, home_country: str | None) -> str:
    if not result.has_data:
        return "No maritime boundary data loaded. Text OP for help."
    if not result.inside_countries:
        msg = ("Outside every national EEZ: high seas, or on land." if result.complete
               else "Outside the EEZ areas loaded here. Do not assume international waters.")
    elif len(result.inside_countries) == 1:
        c = result.inside_countries[0]
        msg = (f"WARNING: you are in {c} waters, not {home_country}. Contact Coast Guard."
               if home_country and c != home_country else f"You are in {c} waters (EEZ).")
    else:
        msg = "Near overlapping EEZ claims: " + ", ".join(result.inside_countries) + "."
    if result.near_border:
        msg += f" ~{result.nearest_km}km from {result.nearest_country} line."
    return msg + " Approx only, not for navigation/legal use."