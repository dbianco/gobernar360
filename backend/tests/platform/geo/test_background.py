"""What each municipality chooses for its maps in Configuración."""

import re

import pytest
from sqlalchemy import select

from gobernar360.platform.geo import backgrounds
from gobernar360.platform.models import AuditLog, MunicipalitySettings
from tests.factories import (
    admin_session,
    configure,
    login,
    make_membership,
    make_municipality,
    make_user,
)
from tests.platform.geo.factories import ADMIN, admin_of, signed_in_admin

SETTINGS = "/api/admin/settings"
KEYED = [b for b in backgrounds.BACKGROUNDS if b.provider]
FREE = [b for b in backgrounds.BACKGROUNDS if not b.provider]


def _save(client, url=f"{SETTINGS}/map", **changes):
    body = {"small_zone_threshold": 5, "map_background": "standard"} | changes
    return client.put(url, json=body)


def _error(response) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


def _shown(client) -> tuple[str, str | None]:
    body = client.get("/api/map-background").json()
    return body["background"]["key"], body["api_key"]


# The list


def test_the_list_is_openstreetmaps():
    assert [b.key for b in FREE] == [
        "standard",
        "humanitarian",
        "cyclosm",
        "germany",
        "france",
        "topographic",
        "public_transport",
    ]
    assert {b.key: b.provider for b in KEYED} == {
        "cycle": "Thunderforest",
        "transport": "Thunderforest",
        "tracestrack": "Tracestrack",
        "maptiler": "MapTiler",
    }


@pytest.mark.parametrize("background", backgrounds.BACKGROUNDS, ids=lambda b: b.key)
def test_every_background_is_complete_and_credited(background):
    assert background.url.startswith("https://")
    placeholders = set(re.findall(r"{(\w+)}", background.url))
    assert {"z", "x", "y"} <= placeholders <= {"s", "z", "x", "y", "apiKey"}
    # A key is asked for exactly where one is used.
    assert ("apiKey" in placeholders) == (background.provider is not None)
    assert backgrounds.OSM in background.attribution
    assert 17 <= background.max_zoom <= 22
    # Large images cover the area of four, one zoom further out.
    assert (background.tile_size, background.zoom_offset) in {(256, 0), (512, -1)}


def test_the_default_needs_no_key_and_keys_do_not_repeat():
    assert backgrounds.find(backgrounds.DEFAULT).provider is None
    assert len({b.key for b in backgrounds.BACKGROUNDS}) == len(backgrounds.BACKGROUNDS)
    assert max(len(b.key) for b in backgrounds.BACKGROUNDS) <= 30


# Choosing


def test_every_member_gets_the_default_until_one_is_chosen(client):
    municipality = make_municipality()
    make_membership(make_user("leo@noetinger.test"), municipality)
    assert client.get("/api/map-background").status_code == 401
    login(client, "leo@noetinger.test")

    assert client.get("/api/map-background").json() == {
        "background": vars(backgrounds.find("standard")),
        "api_key": None,
    }


@pytest.mark.parametrize("background", FREE, ids=lambda b: b.key)
def test_backgrounds_without_a_key_are_chosen_as_they_are(client, background):
    signed_in_admin(client)

    saved = _save(client, map_background=background.key)

    assert saved.status_code == 200
    assert (saved.json()["map_background"], saved.json()["map_api_key"]) == (background.key, None)
    assert _shown(client) == (background.key, None)


@pytest.mark.parametrize("background", KEYED, ids=lambda b: b.key)
def test_backgrounds_with_a_key_need_the_municipalitys(client, background):
    signed_in_admin(client)

    refused = _save(client, map_background=background.key)
    assert refused.json()["error"] == {
        "code": "map_api_key_required",
        "message": "This map needs a key from its provider.",
    }
    assert refused.status_code == 422
    assert _shown(client) == ("standard", None)
    saved = _save(client, map_background=background.key, map_api_key="aB9._-")
    assert saved.json()["map_api_key"] == "aB9._-"
    assert _shown(client) == (background.key, "aB9._-")


def test_a_key_nobody_uses_is_not_kept(client):
    signed_in_admin(client)
    _save(client, map_background="cycle", map_api_key="abc")

    _save(client, map_background="france", map_api_key="abc")

    assert client.get(SETTINGS).json()["map_api_key"] is None
    assert _shown(client) == ("france", None)


@pytest.mark.parametrize("key", ["", " ", "a b", "a&b=c", "a/b", "a?b", "ñ", "a\n", "a" * 101])
def test_a_key_is_only_what_keys_are_made_of(client, key):
    """It ends up in an address every member's browser asks for."""
    signed_in_admin(client)

    refused = _save(client, map_background="cycle", map_api_key=key)

    assert _error(refused) == (422, "validation_error")
    assert _save(client, map_background="cycle", map_api_key="a" * 100).status_code == 200


def test_only_the_backgrounds_of_the_list_can_be_chosen(client):
    signed_in_admin(client)

    for key in ("", "other", "https://tiles.example.test/{z}/{x}/{y}.png"):
        assert _error(_save(client, map_background=key)) == (422, "invalid_reference")


def test_a_background_taken_off_the_list_becomes_the_default(client):
    municipality = signed_in_admin(client)
    with admin_session() as session, session.begin():
        session.add(
            MunicipalitySettings(
                municipality_id=municipality.id, map_background="gone", map_api_key="abc"
            )
        )

    assert client.get(SETTINGS).json()["map_background"] == "standard"
    assert _shown(client) == ("standard", None)


# The threshold


@pytest.mark.parametrize(("threshold", "status"), [(1, 422), (2, 200), (100, 200), (101, 422)])
def test_the_threshold_has_limits(client, threshold, status):
    signed_in_admin(client)

    assert _save(client, small_zone_threshold=threshold).status_code == status


@pytest.mark.parametrize("threshold", [None, "5", 5.5, True])
def test_the_threshold_is_a_whole_number(client, threshold):
    signed_in_admin(client)

    assert _error(_save(client, small_zone_threshold=threshold)) == (422, "validation_error")


# The rest of the configuration


def test_the_parts_of_the_configuration_do_not_undo_each_other(client):
    municipality = signed_in_admin(client)
    configure(municipality, notification_emails=["jefa@noetinger.test"], sso=True)

    _save(client, small_zone_threshold=9, map_background="cyclosm")
    after_map = client.get(SETTINGS).json()
    client.put(SETTINGS, json={"notification_emails": [], "sso_enabled": False})
    after_rest = client.get(SETTINGS).json()

    assert (after_map["notification_emails"], after_map["sso_enabled"]) == (
        ["jefa@noetinger.test"],
        True,
    )
    assert (after_rest["small_zone_threshold"], after_rest["map_background"]) == (9, "cyclosm")


def test_changes_are_audited_without_the_key(client):
    signed_in_admin(client)

    _save(client, small_zone_threshold=7, map_background="cycle", map_api_key="abc123")

    with admin_session() as session:
        [entry] = session.scalars(
            select(AuditLog).where(AuditLog.entity_type == "municipality_settings")
        )
        row = session.scalars(select(MunicipalitySettings)).one()
    assert entry.changes == {
        "small_zone_threshold": 7,
        "map_background": "cycle",
        "map_api_key_set": True,
    }
    assert row.updated_by is not None


def test_each_municipality_has_its_own_and_only_administrators_change_it(client):
    noetinger, saira = make_municipality(), make_municipality("Saira")
    admin_of(noetinger)
    admin_of(saira, "admin@saira.test")
    make_membership(make_user("carla@noetinger.test"), noetinger, grants={"projects": "admin"})
    login(client, ADMIN)
    _save(client, map_background="cycle", map_api_key="abc")
    client.post("/api/auth/logout")

    login(client, "admin@saira.test")
    assert _shown(client) == ("standard", None)
    assert client.get(SETTINGS).json()["small_zone_threshold"] == 5
    client.post("/api/auth/logout")
    login(client, "carla@noetinger.test")
    assert _shown(client) == ("cycle", "abc")
    assert _error(_save(client)) == (403, "forbidden")


def test_the_operator_sets_it_for_any_municipality(client):
    noetinger = make_municipality()
    make_user("operador@example.test", operator=True)
    admin_of(noetinger)
    login(client, "operador@example.test")
    url = f"/api/platform/municipalities/{noetinger.id}/settings"

    assert _save(client, f"{url}/map", map_background="topographic").status_code == 200

    assert client.get(url).json()["map_background"] == "topographic"
    client.post("/api/auth/logout")
    login(client, ADMIN)
    assert _shown(client) == ("topographic", None)
