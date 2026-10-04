"""Pure-Python point-in-polygon + distance-to-boundary for GeoJSON Polygon/MultiPolygon.

Ray-casting algorithm. Good enough for an approximate "which EEZ is this point in"
check — NOT survey-grade, no geodesic correction, no datum handling.
"""

from __future__ import annotations

import math

Point = tuple[float, float]          # (lon, lat)
Ring = list[Point]
Polygon = list[Ring]                 # first ring = outer, rest = holes


def _point_in_ring(lon: float, lat: float, ring: Ring) -> bool:
    inside = False
    x, y = lon, lat
    x1, y1 = ring[-1]
    for x2, y2 in ring:
        if (y1 > y) != (y2 > y):
            x_int = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < x_int:
                inside = not inside
        x1, y1 = x2, y2
    return inside


def point_in_polygon(lon: float, lat: float, polygon: Polygon) -> bool:
    if not polygon or not _point_in_ring(lon, lat, polygon[0]):
        return False
    return not any(_point_in_ring(lon, lat, hole) for hole in polygon[1:])


def point_in_multipolygon(lon: float, lat: float, polygons: list[Polygon]) -> bool:
    return any(point_in_polygon(lon, lat, p) for p in polygons)


def _km_per_degree(lat: float) -> tuple[float, float]:
    return 111.32, max(111.32 * math.cos(math.radians(lat)), 1e-6)


def _dist_to_segment_km(p: Point, a: Point, b: Point, lat_km: float, lon_km: float) -> float:
    px, py = p[0] * lon_km, p[1] * lat_km
    ax, ay = a[0] * lon_km, a[1] * lat_km
    bx, by = b[0] * lon_km, b[1] * lat_km
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def distance_to_multipolygon_km(lon: float, lat: float, polygons: list[Polygon]) -> float:
    lat_km, lon_km = _km_per_degree(lat)
    best = math.inf
    for poly in polygons:
        for ring in poly:
            n = len(ring)
            for i in range(n):
                best = min(best, _dist_to_segment_km((lon, lat), ring[i], ring[(i + 1) % n], lat_km, lon_km))
    return best