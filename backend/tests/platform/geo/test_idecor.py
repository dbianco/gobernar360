"""Reading IDECOR: how it is asked, what counts as an answer, and files in its place."""

import json
from pathlib import Path

import httpx2
import pytest

from gobernar360.platform.geo import idecor
from gobernar360.platform.geo.idecor import Directory, IdecorError, Wfs

SAMPLES = Path(__file__).parent / "idecor_samples"
METRIC = {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::22174"}}
EXCEPTION = b'<?xml version="1.0"?><ows:ExceptionReport/>'


def _collection(*features, crs=METRIC) -> bytes:
    return json.dumps({"type": "FeatureCollection", "features": features, "crs": crs}).encode()


class Server:
    """Answers one after another, and what was asked."""

    def __init__(self, *answers) -> None:
        self.answers = list(answers)
        self.requests: list[httpx2.Request] = []
        self.waits: list[float] = []

    def wfs(self) -> Wfs:
        client = httpx2.Client(transport=httpx2.MockTransport(self._answer))
        return Wfs(client, self.waits.append)

    def _answer(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        status, body = answer if isinstance(answer, tuple) else (200, answer)
        return httpx2.Response(status, content=body)


# Asking


def test_the_radius_is_asked_for_by_its_key_in_metres():
    server = Server(_collection({"id": 1}))

    answer = server.wfs().radius("360124")

    [request] = server.requests
    assert str(request.url).startswith(
        "https://idecor-ws.mapascordoba.gob.ar/geoserver/wfs?service=WFS"
    )
    assert dict(request.url.params) == {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": "idecor:radios_urbanos",
        "outputFormat": "application/json",
        "srsName": "EPSG:22174",
        "cql_filter": "key='360124'",
    }
    assert request.headers["user-agent"] == "gobernar360"
    assert (answer.features, answer.srid, answer.source) == ([{"id": 1}], 22174, str(request.url))
    assert server.waits == []


def test_facilities_are_asked_for_by_their_box_latitude_first():
    server = Server(_collection())

    answer = server.wfs().facilities("Centros_Salud", (-62.34, -32.38, -62.28, -32.33))

    [request] = server.requests
    assert request.url.params["typeNames"] == "idecor:Centros_Salud"
    assert request.url.params["BBOX"] == "-32.38,-62.34,-32.33,-62.28,urn:ogc:def:crs:EPSG::4326"
    assert "cql_filter" not in request.url.params
    assert answer.features == []


def test_without_a_client_of_the_callers_one_with_a_time_limit_is_opened():
    assert Wfs()._http.timeout == httpx2.Timeout(30)


# Answers that do not count


@pytest.mark.parametrize(
    "bad",
    [
        (500, b"oops"),
        (503, _collection()),
        (400, EXCEPTION),
        EXCEPTION,
        b"[]",
        b'{"type": "FeatureCollection"}',
        b'{"features": {}}',
        httpx2.ConnectError("refused"),
        httpx2.ReadTimeout("slow"),
    ],
    ids=str,
)
def test_an_answer_that_does_not_count_is_asked_for_again(bad):
    server = Server(bad, _collection({"id": 7}))

    assert server.wfs().radius("360124").features == [{"id": 7}]
    assert server.waits == [1]


def test_after_four_attempts_it_says_what_was_wrong():
    server = Server((502, b""), EXCEPTION, httpx2.ConnectError("refused"), EXCEPTION, _collection())

    with pytest.raises(IdecorError) as raised:
        server.wfs().facilities("Centros_Salud", (0, 0, 1, 1))

    assert (
        str(raised.value) == "IDECOR did not answer for Centros_Salud after 4 attempts: "
        "the answer is not JSON"
    )
    assert len(server.requests) == 4
    assert server.waits == [1, 2, 4]


# The system of the coordinates


@pytest.mark.parametrize(
    ("crs", "srid"),
    [
        (METRIC, 22174),
        ({"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::4326"}}, 4326),
        # GeoJSON says nothing when it is in degrees.
        (None, 4326),
    ],
)
def test_the_answer_says_its_coordinate_system(crs, srid):
    assert Server(_collection(crs=crs)).wfs().radius("360124").srid == srid


@pytest.mark.parametrize(
    "crs",
    [
        {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::3857"}},
        {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::122174"}},
        {"type": "name", "properties": {}},
        {"type": "name"},
        "EPSG:22174",
    ],
)
def test_another_system_is_refused_rather_than_guessed(crs):
    with pytest.raises(IdecorError, match="radios_urbanos: unknown coordinate system"):
        Server(_collection(crs=crs)).wfs().radius("360124")


# From files


def test_a_directory_gives_the_file_in_metres_first():
    directory = Directory(SAMPLES, "noetinger")

    radius = directory.radius("360124")
    schools = directory.facilities("establecimientos_educativos", (0, 0, 1, 1))

    assert (radius.srid, len(radius.features)) == (22174, 1)
    assert radius.source == str(SAMPLES / "noetinger_radios_urbanos_epsg22174.json")
    assert (schools.srid, len(schools.features)) == (4326, 11)
    assert schools.source == str(SAMPLES / "noetinger_establecimientos_educativos.geojson")


def test_a_collection_without_features_is_named(tmp_path):
    (tmp_path / "saira_radios_urbanos.geojson").write_text('{"type": "FeatureCollection"}')

    with pytest.raises(IdecorError) as raised:
        Directory(tmp_path, "saira").radius("1")

    assert str(raised.value) == "saira_radios_urbanos.geojson: the answer has no features."


def test_a_file_in_another_system_names_its_layer(tmp_path):
    crs = {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::3857"}}
    (tmp_path / "saira_Centros_Salud.geojson").write_bytes(_collection(crs=crs))

    with pytest.raises(IdecorError) as raised:
        Directory(tmp_path, "saira").facilities(idecor.HEALTH, (0, 0, 1, 1))

    assert str(raised.value) == (
        "Centros_Salud: unknown coordinate system 'urn:ogc:def:crs:EPSG::3857'."
    )


def test_without_the_file_it_says_which_names_it_looked_for(tmp_path):
    with pytest.raises(IdecorError) as raised:
        Directory(tmp_path, "saira").radius("360124")

    assert str(raised.value) == (
        "There is no saira_radios_urbanos_epsg22174.json or "
        f"saira_radios_urbanos.geojson in {tmp_path}."
    )


def test_a_file_that_is_not_a_collection_is_named(tmp_path):
    (tmp_path / "saira_Centros_Salud.geojson").write_bytes(EXCEPTION)

    with pytest.raises(IdecorError) as raised:
        Directory(tmp_path, "saira").facilities(idecor.HEALTH, (0, 0, 1, 1))

    assert str(raised.value) == "saira_Centros_Salud.geojson: the answer is not JSON."
