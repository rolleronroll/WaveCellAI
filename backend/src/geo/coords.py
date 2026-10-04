"""Parse a lat/lon pair out of free-form SMS text (e.g. '21.43,91.97' or '21.43N 91.97E')."""

from __future__ import annotations

import re
from dataclasses import dataclass

_COORD = re.compile(
    r"(-?\d{1,3}(?:\.\d+)?)\s*°?\s*([NnSs])?\s*[,/\s]\s*(-?\d{1,3}(?:\.\d+)?)\s*°?\s*([EeWw])?"
)


@dataclass(frozen=True)
class Coords:
    lat: float
    lon: float


def parse_coords(text: str) -> Coords | None:
    m = _COORD.search(text)
    if not m:
        return None
    lat = -abs(float(m.group(1))) if (m.group(2) or "").lower() == "s" else float(m.group(1))
    lon = -abs(float(m.group(3))) if (m.group(4) or "").lower() == "w" else float(m.group(3))
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        return None
    return Coords(lat=lat, lon=lon)