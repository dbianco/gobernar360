"""Public facilities on the maps, and who says where the municipality is."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from gobernar360.platform.geo import backgrounds, reference_router
from gobernar360.platform.geo.models import ReferenceFeature
from gobernar360.platform.models import AuditLog, MunicipalitySettings
from tests.factories import admin_session, login, make_membership, make_municipality, make_user
from tests.platform.geo.factories import ADMIN, admin_of, point, signed_in_admin

LAYERS = "/api/geo/reference-layers"
WORLD = "-180,-90,180,90"
NOW = datetime(2026, 11, 25, 12, tzinfo=UTC)
CONAE = "Localidades:Cordoba_Noetinger_2023"


def _facility(municipality, name="Hospital", x=0.5, y=0.5, layer="health", **fields):
    row = ReferenceFeature(
        municipality_id=municipality.id,
        layer=layer,
        name=name,
        location=point(x, y),
        **(
            {
                "source_id": name,
                "properties": {"address": "San Martín 1"},
                "source_url": "https://idecor.test",
                "imported_at": NOW,
            }
            | fields
        ),
    )
    with admin_session() as session, session.begin():
        session.add(row)
    return row


def _names(client, layer="health", bbox=WORLD) -> list[str]:
    response = client.get(f"{LAYERS}/{layer}", params={"bbox": bbox})
    assert response.status_code == 200, response.text
    return [feature["name"] for feature in response.json()["features"]]


def _error(response) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


# On the maps


def test_any_member_sees_the_facilities_without_any_dashboard(client):
    municipality = make_municipality()
    hospital = _facility(municipality)
    make_membership(make_user("sofia@noetinger.test"), municipality)
    assert client.get(LAYERS).status_code == 401
    assert client.get(f"{LAYERS}/health", params={"bbox": WORLD}).status_code == 401
    login(client, "sofia@noetinger.test")

    assert client.get(f"{LAYERS}/health", params={"bbox": WORLD}).json() == {
        "features": [
            {
                "id": str(hospital.id),
                "name": "Hospital",
                "properties": {"address": "San Martín 1"},
                "geometry": point(0.5, 0.5),
            }
        ],
        "truncated": False,
    }


def test_the_layers_with_something_to_show(client):
    municipality = signed_in_admin(client)
    assert client.get(LAYERS).json() == []
    later = datetime(2026, 11, 26, 12, tzinfo=UTC)
    _facility(municipality, "B", layer="schools")
    _facility(municipality, "A", layer="schools", imported_at=later)
    _facility(municipality)

    assert [
        (layer["layer"], layer["features"], datetime.fromisoformat(layer["imported_at"]))
        for layer in client.get(LAYERS).json()
    ] == [("health", 1, NOW), ("schools", 2, later)]


def test_only_what_is_inside_the_visible_area_comes(client):
    municipality = signed_in_admin(client)
    for name, x in (("Adentro", 0.5), ("En el borde", 1), ("Afuera", 1.01)):
        _facility(municipality, name, x=x)
    _facility(municipality, "Escuela", layer="schools")

    assert _names(client, bbox="-62,-32,-61.99,-31.99") == ["Adentro", "En el borde"]
    assert _names(client, "schools") == ["Escuela"]


def test_they_come_by_name_and_no_more_than_can_be_drawn(client, monkeypatch):
    municipality = signed_in_admin(client)
    for name in ("C", "A", "B"):
        _facility(municipality, name)
    assert _names(client) == ["A", "B", "C"]

    monkeypatch.setattr(reference_router, "MAX_FEATURES", 3)
    assert client.get(f"{LAYERS}/health", params={"bbox": WORLD}).json()["truncated"] is False
    monkeypatch.setattr(reference_router, "MAX_FEATURES", 2)
    body = client.get(f"{LAYERS}/health", params={"bbox": WORLD}).json()
    assert ([f["name"] for f in body["features"]], body["truncated"]) == (["A", "B"], True)


def test_an_area_or_a_layer_that_does_not_exist(client):
    signed_in_admin(client)

    assert _error(client.get(f"{LAYERS}/health", params={"bbox": "x"})) == (422, "invalid_area")
    assert _error(client.get(f"{LAYERS}/health")) == (422, "validation_error")
    assert _error(client.get(f"{LAYERS}/parcels", params={"bbox": WORLD})) == (
        422,
        "validation_error",
    )


def test_a_municipality_never_sees_the_facilities_of_another(client):
    _facility(signed_in_admin(client), "Propio")
    saira = make_municipality("Saira")
    _facility(saira, "Ajeno")
    _facility(saira, "Ajeno", layer="schools")

    assert _names(client) == ["Propio"]
    assert _names(client, "schools") == []
    assert [(layer["layer"], layer["features"]) for layer in client.get(LAYERS).json()] == [
        ("health", 1)
    ]


def test_nobody_writes_them_through_the_api(client):
    signed_in_admin(client)

    for method in ("post", "put", "patch", "delete"):
        assert getattr(client, method)(f"{LAYERS}/health").status_code == 405


def test_the_database_keeps_one_of_each_and_only_known_layers():
    municipality = make_municipality()
    _facility(municipality)
    for fields in ({}, {"layer": "parcels"}):
        with pytest.raises(IntegrityError):
            _facility(municipality, **fields)
    # The same identifier in another layer, or another town, is another facility.
    _facility(municipality, layer="schools")
    _facility(make_municipality("Saira"))


# Where the municipality is, in Configuración


def _operator(client):
    make_user("operador@example.test", operator=True)
    login(client, "operador@example.test")


def _geography(client, municipality, **changes):
    body = {"idecor_key": "360124", "conae_layer": CONAE} | changes
    return client.put(
        f"/api/platform/municipalities/{municipality.id}/settings/geography", json=body
    )


def _offered(settings: dict) -> dict | None:
    return next((b for b in settings["map_backgrounds"] if b["key"] == "satellite"), None)


def test_the_operator_sets_where_the_municipality_is(client):
    municipality = make_municipality()
    _operator(client)

    saved = _geography(client, municipality)

    assert saved.status_code == 200
    assert (saved.json()["idecor_key"], saved.json()["conae_layer"]) == ("360124", CONAE)
    url = f"/api/platform/municipalities/{municipality.id}/settings"
    assert client.get(url).json() == saved.json()
    with admin_session() as session:
        [entry] = session.scalars(select(AuditLog))
        row = session.scalars(select(MunicipalitySettings)).one()
    assert (entry.entity_type, entry.action) == ("municipality_settings", "update")
    assert entry.changes == {"idecor_key": "360124", "conae_layer": CONAE}
    assert row.updated_by == entry.user_id is not None
    cleared = _geography(client, municipality, idecor_key=None, conae_layer=None).json()
    assert (cleared["idecor_key"], cleared["conae_layer"]) == (None, None)


def test_the_municipalitys_administrator_sees_it_and_cannot_change_it(client):
    municipality = make_municipality()
    _operator(client)
    _geography(client, municipality)
    client.post("/api/auth/logout")
    admin_of(municipality)
    login(client, ADMIN)

    seen = client.get("/api/admin/settings").json()

    assert (seen["idecor_key"], seen["conae_layer"]) == ("360124", CONAE)
    assert _error(_geography(client, municipality, idecor_key="111111")) == (403, "forbidden")
    own = client.put("/api/admin/settings/geography", json={"idecor_key": "1", "conae_layer": None})
    assert own.status_code == 404 or own.status_code == 405
    # Nor through what they can save.
    assert _error(
        client.put(
            "/api/admin/settings/map",
            json={
                "small_zone_threshold": 5,
                "map_background": "standard",
                "idecor_key": "111111",
            },
        )
    ) == (422, "validation_error")
    client.put(
        "/api/admin/settings",
        json={
            "notification_emails": [],
            "sso_enabled": True,
            "idecor_key": "1",
            "conae_layer": "x",
        },
    )
    client.put(
        "/api/admin/settings/map", json={"small_zone_threshold": 9, "map_background": "cyclosm"}
    )
    after = client.get("/api/admin/settings").json()
    assert (after["idecor_key"], after["conae_layer"]) == ("360124", CONAE)


@pytest.mark.parametrize(
    "bad",
    [
        {"idecor_key": "36012"},
        {"idecor_key": "3601245"},
        {"idecor_key": "36012a"},
        {"idecor_key": "٣٦٠١٢٤"},
        {"idecor_key": "360124\n"},
        {"idecor_key": ""},
        {"conae_layer": ""},
        {"conae_layer": "a/../b"},
        {"conae_layer": "capa{z}"},
        {"conae_layer": "a b"},
        {"conae_layer": "a?b"},
        {"conae_layer": "x" * 101},
        {"other": 1},
    ],
)
def test_what_is_not_a_key_or_a_layer_is_refused(client, bad):
    municipality = make_municipality()
    _operator(client)

    assert _error(_geography(client, municipality, **bad)) == (422, "validation_error")
    with admin_session() as session:
        assert session.scalars(select(MunicipalitySettings)).all() == []


def test_the_longest_layer_name_is_accepted(client):
    municipality = make_municipality()
    _operator(client)

    assert _geography(client, municipality, conae_layer="x" * 100).status_code == 200


# The satellite image


def test_the_satellite_image_is_offered_only_where_there_is_one(client):
    noetinger, saira = make_municipality(), make_municipality("Saira")
    _operator(client)
    _geography(client, noetinger)
    client.post("/api/auth/logout")
    admin_of(noetinger)
    admin_of(saira, "admin@saira.test")
    save = {"small_zone_threshold": 5, "map_background": "satellite"}

    login(client, ADMIN)
    assert _offered(client.get("/api/admin/settings").json()) == {
        "key": "satellite",
        "url": "https://geotematico01.conae.gov.ar/geoserver/gwc/service/wmts/rest/"
        "Localidades:Cordoba_Noetinger_2023/raster/EPSG:900913/EPSG:900913:{z}/{y}/{x}"
        "?format=image/png",
        "attribution": "Imagen: CONAE – Pleiades Neo 2023",
        "max_zoom": 19,
        "provider": None,
        "tile_size": 256,
        "zoom_offset": 0,
    }
    assert client.put("/api/admin/settings/map", json=save).json()["map_background"] == "satellite"
    chosen = client.get("/api/map-background").json()
    assert (chosen["background"]["key"], chosen["api_key"]) == ("satellite", None)
    assert "Cordoba_Noetinger_2023" in chosen["background"]["url"]
    client.post("/api/auth/logout")

    login(client, "admin@saira.test")
    assert _offered(client.get("/api/admin/settings").json()) is None
    assert _error(client.put("/api/admin/settings/map", json=save)) == (422, "invalid_reference")


def test_a_layer_without_a_year_claims_none(client):
    def attribution(layer):
        return backgrounds.find("satellite", layer).attribution

    assert attribution("Localidades:Cordoba_Saira") == "Imagen: CONAE – Pleiades Neo"
    assert attribution("Localidades:Cordoba_2023_Saira") == "Imagen: CONAE – Pleiades Neo"
    assert attribution("Localidades:Cordoba_Saira_2021") == "Imagen: CONAE – Pleiades Neo 2021"


def test_a_municipality_left_without_its_layer_goes_back_to_the_default(client):
    municipality = make_municipality()
    _operator(client)
    _geography(client, municipality)
    url = f"/api/platform/municipalities/{municipality.id}/settings"
    client.put(f"{url}/map", json={"small_zone_threshold": 5, "map_background": "satellite"})

    saved = _geography(client, municipality, conae_layer=None).json()

    assert (saved["map_background"], _offered(saved)) == ("standard", None)
    client.post("/api/auth/logout")
    admin_of(municipality)
    login(client, ADMIN)
    assert client.get("/api/map-background").json()["background"]["key"] == "standard"
