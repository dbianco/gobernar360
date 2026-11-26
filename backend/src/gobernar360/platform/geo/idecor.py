"""Reading IDECOR, the spatial data infrastructure of the Province of Córdoba.

Over its WFS or from a directory with its answers. What it publishes, and how its server
behaves, is in docs/idecor/README.md:

- it answers some valid requests with an XML exception or a 5xx, so every request is
  retried and an answer only counts when it is a GeoJSON collection;
- attribute filters time out on the large layers, so those are asked for by their box and
  narrowed here;
- in degrees it rounds to about ten metres, so the metric system it stores is asked for.
"""

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import httpx2

WFS = "https://idecor-ws.mapascordoba.gob.ar/geoserver/wfs"
# POSGAR 94 / Argentina 4: metres, the system IDECOR stores.
METRIC_SRID = 22174
DEGREES_SRID = 4326

RADIUS = "radios_urbanos"
HEALTH = "Centros_Salud"
SCHOOLS = "establecimientos_educativos"

ATTEMPTS = 4
TIMEOUT_SECONDS = 30
HEADERS = {"User-Agent": "gobernar360"}

# West, south, east and north, in degrees.
Box = tuple[float, float, float, float]


class IdecorError(Exception):
    """IDECOR did not give what was asked for; the message is for whoever runs the import."""


@dataclass(frozen=True)
class Answer:
    features: list[Any]
    # System of the coordinates.
    srid: int
    # Where it was read.
    source: str


class Source(Protocol):
    def radius(self, key: str) -> Answer: ...

    def facilities(self, layer: str, box: Box) -> Answer: ...


def _collection(content: bytes) -> dict[str, Any]:
    """The GeoJSON collection in an answer, which may be an XML exception instead."""
    try:
        data = json.loads(content)
    except ValueError as error:
        raise IdecorError("the answer is not JSON") from error
    if not isinstance(data, dict) or not isinstance(data.get("features"), list):
        raise IdecorError("the answer has no features")
    return data


def _srid(data: dict[str, Any], layer: str) -> int:
    """The system the answer says its coordinates are in. GeoJSON without one is in degrees."""
    crs = data.get("crs")
    if crs is None:
        return DEGREES_SRID
    properties = crs.get("properties") if isinstance(crs, dict) else None
    name = str(properties.get("name", "")) if isinstance(properties, dict) else ""
    for srid in (METRIC_SRID, DEGREES_SRID):
        if name.endswith(f":{srid}"):
            return srid
    raise IdecorError(f"{layer}: unknown coordinate system {name!r}.")


class Wfs:
    """The live service."""

    def __init__(
        self, http: httpx2.Client | None = None, sleep: Callable[[float], None] = time.sleep
    ) -> None:
        self._http = http or httpx2.Client(timeout=TIMEOUT_SECONDS)
        self._sleep = sleep

    def radius(self, key: str) -> Answer:
        # A small layer: the only one whose attribute filter answers.
        return self._get(RADIUS, cql_filter=f"key='{key}'")

    def facilities(self, layer: str, box: Box) -> Answer:
        west, south, east, north = box
        # With this name of the system, latitude goes first.
        bbox = f"{south},{west},{north},{east},urn:ogc:def:crs:EPSG::{DEGREES_SRID}"
        return self._get(layer, BBOX=bbox)

    def _get(self, layer: str, **narrowed: str) -> Answer:
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": f"idecor:{layer}",
            "outputFormat": "application/json",
            "srsName": f"EPSG:{METRIC_SRID}",
            **narrowed,
        }
        problem: Exception | None = None
        for attempt in range(ATTEMPTS):
            if attempt:
                self._sleep(2 ** (attempt - 1))
            try:
                response = self._http.get(WFS, params=params, headers=HEADERS)
                response.raise_for_status()
                data = _collection(response.content)
            except (httpx2.HTTPError, IdecorError) as error:
                problem = error
                continue
            return Answer(data["features"], _srid(data, layer), str(response.url))
        raise IdecorError(
            f"IDECOR did not answer for {layer} after {ATTEMPTS} attempts: {problem}"
        ) from problem


class Directory:
    """Answers saved in files, named `<prefix>_<layer>_epsg22174.json` or, when there is no
    such file, `<prefix>_<layer>.geojson` (as docs/idecor/samples). Opens no connection."""

    def __init__(self, path: Path, prefix: str) -> None:
        self._path = path
        self._prefix = prefix

    def radius(self, key: str) -> Answer:
        return self._read(RADIUS)

    def facilities(self, layer: str, box: Box) -> Answer:
        return self._read(layer)

    def _read(self, layer: str) -> Answer:
        names = [
            f"{self._prefix}_{layer}_epsg{METRIC_SRID}.json",
            f"{self._prefix}_{layer}.geojson",
        ]
        file = next((f for name in names if (f := self._path / name).is_file()), None)
        if file is None:
            raise IdecorError(f"There is no {' or '.join(names)} in {self._path}.")
        try:
            data = _collection(file.read_bytes())
        except IdecorError as error:
            raise IdecorError(f"{file.name}: {error}.") from error
        return Answer(data["features"], _srid(data, layer), str(file))
