"""Checks on the GeoJSON people draw or upload, before it reaches the database."""

from collections.abc import Iterator
from typing import Any

from gobernar360.core.errors import invalid_boundary, invalid_location, zone_not_closed
from gobernar360.platform.geo.located import LINE, POINT

# A closed ring needs three corners and its first one again.
MIN_RING_POSITIONS = 4
# Far more than a neighbourhood or a street needs; keeps one request from being huge.
MAX_BOUNDARY_POSITIONS = 10_000
MAX_LINE_POSITIONS = 1_000


def _position(value: Any) -> list[float] | None:
    """[longitude, latitude] when `value` is a GeoJSON position; the altitude is dropped."""
    if not isinstance(value, list) or not 2 <= len(value) <= 3:
        return None
    if any(isinstance(n, bool) or not isinstance(n, int | float) for n in value):
        return None
    longitude, latitude = float(value[0]), float(value[1])
    # Also false for NaN and infinities.
    if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
        return None
    return [longitude, latitude]


def location_geometry(geometry: Any, kinds: tuple[str, ...]) -> dict[str, Any]:
    """A record's location as a clean GeoJSON geometry of one of `kinds`."""
    kind = geometry.get("type") if isinstance(geometry, dict) else None
    if kind not in kinds:
        raise invalid_location(f"The location must be a GeoJSON {' or '.join(kinds)}.")
    coordinates = geometry.get("coordinates")
    if kind == POINT:
        position = _position(coordinates)
        if position is None:
            raise invalid_location("The point needs a valid longitude and latitude.")
        return {"type": POINT, "coordinates": position}
    positions = [_position(p) for p in coordinates] if isinstance(coordinates, list) else []
    if None in positions or len(positions) > MAX_LINE_POSITIONS:
        raise invalid_location("Every point of the line needs a valid longitude and latitude.")
    if len({tuple(p) for p in positions}) < 2:
        raise invalid_location("The line needs at least two different points.")
    return {"type": LINE, "coordinates": positions}


def _rings(polygons: Any) -> Iterator[Any]:
    for polygon in polygons if isinstance(polygons, list) else [None]:
        yield from polygon if isinstance(polygon, list) and polygon else [None]


def boundary_geometry(geometry: Any) -> dict[str, Any]:
    """A zone's boundary as a clean GeoJSON MultiPolygon whose rings are closed.

    Whether it crosses itself is for the database to say (`zones.check_valid`).
    """
    kind = geometry.get("type") if isinstance(geometry, dict) else None
    if kind not in ("Polygon", "MultiPolygon"):
        raise invalid_boundary("The boundary must be a GeoJSON Polygon or MultiPolygon.")
    coordinates = geometry.get("coordinates")
    if not coordinates:
        raise invalid_boundary("The boundary is empty.")
    polygons = [coordinates] if kind == "Polygon" else coordinates
    total = 0
    clean: list[list[list[float]]] = []
    for ring in _rings(polygons):
        positions = [_position(p) for p in ring] if isinstance(ring, list) else [None]
        if None in positions:
            raise invalid_boundary("Every corner needs a valid longitude and latitude.")
        if len(positions) < MIN_RING_POSITIONS:
            raise invalid_boundary("The boundary needs at least three corners.")
        if positions[0] != positions[-1]:
            raise zone_not_closed()
        total += len(positions)
        clean.append(positions)
    if total > MAX_BOUNDARY_POSITIONS:
        raise invalid_boundary(f"The boundary has more than {MAX_BOUNDARY_POSITIONS} corners.")
    # The rings come in order, so they are dealt back to their polygons.
    rings = iter(clean)
    return {
        "type": "MultiPolygon",
        "coordinates": [[next(rings) for _ in polygon] for polygon in polygons],
    }
