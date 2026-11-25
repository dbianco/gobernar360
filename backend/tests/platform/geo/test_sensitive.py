"""Where a household lives is for editors and above; viewers get counts that point at no one."""

import csv
import dataclasses
import io
import json
from datetime import date

import pytest
from sqlalchemy import func

from gobernar360.dashboards import registry
from gobernar360.platform.clock import get_today
from gobernar360.platform.models import MunicipalitySettings
from tests.factories import admin_session, login, make_membership, make_municipality, make_user
from tests.platform.geo.factories import make_zone, point, square
from tests.social.factories import (
    make_benefit,
    make_delivery,
    make_household,
    make_intervention,
    make_intervention_type,
    make_social_person,
)

BASE = "/api/dashboards/social"
HOUSEHOLDS = f"{BASE}/geo/households"
WORLD = "-180,-90,180,90"
TODAY = date(2026, 6, 15)


@pytest.fixture
def municipality(client):
    client.app.dependency_overrides[get_today] = lambda: TODAY
    municipality = make_municipality()
    for email, level in (("leo@noetinger.test", "viewer"), ("carla@noetinger.test", "editor")):
        make_membership(make_user(email), municipality, grants={"social": level})
    return municipality


def _sign_in(client, name="leo"):
    client.post("/api/auth/logout")
    login(client, f"{name}@noetinger.test")


def _settle(municipality, count: int, x: float, prefix: str):
    return [
        make_household(municipality, f"{prefix} {n}", location=point(x + n / 100, 0.5))
        for n in range(count)
    ]


def _neighbourhoods(municipality, **sizes: int):
    households = {}
    for index, (name, size) in enumerate(sizes.items()):
        make_zone(municipality, name, square(index * 2, 0))
        households[name] = _settle(municipality, size, index * 2 + 0.1, name)
    return households


def _counts(client, metric="households", **params):
    body = client.get(f"{HOUSEHOLDS}/zones", params=params).json()
    return {row["zone"]["name"]: row["values"][metric] for row in body["zones"]}


@pytest.mark.parametrize("zoom", [0, 10, 17, 22])
def test_a_viewer_receives_no_household_from_the_map(client, municipality, zoom):
    _neighbourhoods(municipality, Sur=6)
    _sign_in(client)

    found = client.get(f"{HOUSEHOLDS}/features", params={"bbox": WORLD, "zoom": zoom}).json()

    assert found == {
        "restricted": True,
        "total": 0,
        "features": [],
        "clusters": [],
        "truncated": False,
    }
    _sign_in(client, "carla")
    found = client.get(f"{HOUSEHOLDS}/features", params={"bbox": WORLD, "zoom": zoom}).json()
    assert (found["restricted"], found["total"]) == (False, 6)


def test_a_viewer_receives_no_household_coordinates_from_anywhere(client, municipality):
    [household, *_] = _neighbourhoods(municipality, Sur=6)["Sur"]
    make_social_person(municipality, household=household, relationship="head")
    _sign_in(client)
    longitude, latitude = household.location["coordinates"]

    answers = [
        client.get(f"{BASE}/households"),
        client.get(f"{BASE}/households/{household.id}"),
        client.get(f"{BASE}/people"),
        client.get(f"{BASE}/summary"),
        client.get(f"{BASE}/reports"),
        client.get(f"{BASE}/export/households.csv"),
        client.get(f"{BASE}/export/people.csv"),
        client.get(f"{HOUSEHOLDS}/zones"),
        client.get(f"{HOUSEHOLDS}/zones.csv"),
        client.get(f"{HOUSEHOLDS}/features", params={"bbox": WORLD, "zoom": 18}),
        client.get("/api/overview"),
    ]

    for answer in answers:
        assert answer.status_code == 200, answer.url
        assert str(longitude) not in answer.text and str(latitude) not in answer.text, answer.url
        assert "coordinates" not in answer.text and "location" not in answer.text.replace(
            "(no location)", ""
        ).replace("unlocated", ""), answer.url


def test_a_viewer_does_not_learn_the_zone_of_one_household(client, municipality):
    [household, *_] = _neighbourhoods(municipality, Sur=6)["Sur"]
    _sign_in(client)
    path = f"{HOUSEHOLDS}/{household.id}/location"

    assert client.get(f"{BASE}/households/{household.id}").json()["zones"] is None
    assert {h["zones"] for h in client.get(f"{BASE}/households").json()["items"]} == {None}
    for refused in (
        client.get(path),
        client.put(path, json={"location": None}),
        client.get(f"{HOUSEHOLDS}/unzoned"),
        client.get(f"{HOUSEHOLDS}/unzoned", params={"reason": "unlocated"}),
    ):
        assert (refused.status_code, refused.json()["error"]["code"]) == (403, "forbidden")
    _sign_in(client, "carla")
    assert client.get(path).json()["location"] == household.location
    [zone] = client.get(f"{BASE}/households/{household.id}").json()["zones"]
    assert zone["name"] == "Sur"
    assert client.get(f"{BASE}/households").json()["items"][0]["zones"] == [zone]


def test_small_zones_are_suppressed_for_viewers_and_not_for_editors(client, municipality):
    _neighbourhoods(municipality, Sur=7, Norte=5, Oeste=4, Este=2)
    _sign_in(client)

    body = client.get(f"{HOUSEHOLDS}/zones").json()

    assert _counts(client) == {"Este": None, "Norte": 5, "Oeste": None, "Sur": 7}
    assert {row["zone"]["name"]: row["suppressed"] for row in body["zones"]} == {
        "Este": True,
        # Shown, though how many of them were helped is not.
        "Norte": True,
        "Oeste": True,
        "Sur": True,
    }
    assert body["threshold"] == 5
    assert all(row["groups"] == [] for row in body["zones"])
    _sign_in(client, "carla")
    body = client.get(f"{HOUSEHOLDS}/zones").json()
    assert _counts(client) == {"Este": 2, "Norte": 5, "Oeste": 4, "Sur": 7}
    assert body["threshold"] is None
    assert not any(row["suppressed"] for row in body["zones"])


def test_a_single_small_zone_cannot_be_worked_out_from_the_total(client, municipality):
    _neighbourhoods(municipality, Sur=9, Norte=6, Oeste=2)
    _sign_in(client)

    body = client.get(f"{HOUSEHOLDS}/zones").json()

    # The total is known, so showing Sur and Norte would tell Oeste.
    assert body["total"]["values"]["households"] == 17
    assert _counts(client) == {"Norte": None, "Oeste": None, "Sur": 9}


def test_households_without_a_zone_are_protected_too(client, municipality):
    _neighbourhoods(municipality, Sur=9, Norte=6)
    _settle(municipality, 1, 50, "Campo")
    make_household(municipality, "Sin lugar")
    _sign_in(client)

    body = client.get(f"{HOUSEHOLDS}/zones").json()

    assert body["outside"]["values"]["households"] is None
    assert body["unlocated"]["values"]["households"] is None
    assert _counts(client) == {"Norte": None, "Sur": 9}


def _set_threshold(municipality, threshold: int) -> None:
    with admin_session() as session, session.begin():
        session.add(
            MunicipalitySettings(municipality_id=municipality.id, small_zone_threshold=threshold)
        )


def test_the_threshold_is_the_municipalitys(client, municipality):
    _set_threshold(municipality, 2)
    # Another municipality's is its own affair.
    _set_threshold(make_municipality("Saira"), 50)
    _neighbourhoods(municipality, Sur=3, Norte=2)
    _sign_in(client)

    assert _counts(client) == {"Norte": 2, "Sur": 3}
    assert client.get(f"{HOUSEHOLDS}/zones").json()["threshold"] == 2


def test_the_administrator_changes_the_threshold_and_viewers_see_it_at_once(client, municipality):
    make_membership(make_user("admin@noetinger.test"), municipality, admin=True, enable=[])
    _neighbourhoods(municipality, Sur=9, Norte=6, Oeste=6)
    _sign_in(client)
    before = _counts(client)
    _sign_in(client, "admin")
    saved = client.put(
        "/api/admin/settings/map",
        json={"small_zone_threshold": 8, "map_background": "standard"},
    )
    assert saved.status_code == 200, saved.text
    _sign_in(client)

    assert before == {"Norte": 6, "Oeste": 6, "Sur": 9}
    assert _counts(client) == {"Norte": None, "Oeste": None, "Sur": 9}
    lines = client.get(f"{HOUSEHOLDS}/zones.csv").text.splitlines()
    assert "Norte,*,*" in lines


def test_households_assisted_count_the_help_of_the_year(client, municipality):
    _set_threshold(municipality, 2)
    homes = _neighbourhoods(municipality, Sur=4, Norte=2)
    benefit, kind = make_benefit(municipality), make_intervention_type(municipality)
    delivered, visited, both, last_year = (
        make_social_person(municipality, f"P{n}", household=home)
        for n, home in enumerate(homes["Sur"])
    )
    relative = make_social_person(municipality, "Hija", household=homes["Sur"][0])
    alone = make_social_person(municipality, "Sola")
    for person in (delivered, relative, both, alone):
        make_delivery(municipality, benefit, person, on=date(2026, 1, 1))
    for person in (visited, both):
        make_intervention(municipality, kind, person, on=date(2026, 12, 31))
    make_delivery(municipality, benefit, last_year, on=date(2025, 12, 31))
    _sign_in(client, "carla")

    assert _counts(client, "assisted") == {"Norte": 0, "Sur": 3}
    assert _counts(client, "assisted", year=2025) == {"Norte": 0, "Sur": 1}
    assert _counts(client, "households", year=2025) == {"Norte": 2, "Sur": 4}
    _sign_in(client)
    # Each figure is hidden on its own.
    assert _counts(client, "assisted") == {"Norte": None, "Sur": 3}
    assert _counts(client) == {"Norte": 2, "Sur": 4}
    assert _counts(client, "assisted", year=2025) == {"Norte": None, "Sur": None}


def test_a_viewer_cannot_search_their_way_to_one_household(client, municipality):
    """Two searches that differ in one household would tell its zone by subtracting."""
    _neighbourhoods(municipality, Sur=9, Norte=6)
    _sign_in(client)

    everything = client.get(f"{HOUSEHOLDS}/zones").json()

    assert _counts(client) == {"Norte": 6, "Sur": 9}
    for q in ("Sur 3", "Sur", "nada"):
        assert client.get(f"{HOUSEHOLDS}/zones", params={"q": q}).json() == everything
        csv_all, csv_found = (
            client.get(f"{HOUSEHOLDS}/zones.csv", params=params).text for params in ({}, {"q": q})
        )
        assert csv_all == csv_found
    _sign_in(client, "carla")
    assert _counts(client, q="Sur 3") == {"Norte": 0, "Sur": 1}


def test_the_household_csv_has_places_only_for_editors(client, municipality):
    [household] = _neighbourhoods(municipality, Sur=1)["Sur"]
    make_household(municipality, "Sin lugar")

    def rows():
        text = client.get(f"{BASE}/export/households.csv").text.lstrip("\ufeff")
        return list(csv.reader(io.StringIO(text)))

    _sign_in(client)
    assert rows() == [
        ["name", "address", "neighborhood", "members", "head"],
        ["Sin lugar", "", "", "0", ""],
        ["Sur 0", "", "", "0", ""],
    ]
    _sign_in(client, "carla")
    longitude, latitude = household.location["coordinates"]
    assert rows() == [
        ["name", "address", "neighborhood", "members", "head", "zones", "latitude", "longitude"],
        ["Sin lugar", "", "", "0", "", "", "", ""],
        ["Sur 0", "", "", "0", "", "Sur", str(latitude), str(longitude)],
    ]


def test_the_csv_by_zone_hides_what_the_screen_hides(client, municipality):
    _neighbourhoods(municipality, Sur=9, Norte=6, Oeste=2)
    _sign_in(client)

    lines = client.get(f"{HOUSEHOLDS}/zones.csv").text.lstrip("\ufeff").splitlines()

    assert lines == [
        "zone,households,assisted",
        "Norte,*,*",
        "Oeste,*,*",
        "Sur,9,*",
        "(outside),*,*",
        "(no location),*,*",
        "(total),17,0",
    ]


def test_the_zone_profile_hides_the_same(client, municipality):
    zone = make_zone(municipality, "Sur", square(0, 0))
    make_zone(municipality, "Norte", square(2, 0))
    _settle(municipality, 3, 0.1, "Sur")
    _settle(municipality, 8, 2.1, "Norte")
    _sign_in(client)

    [section] = client.get(f"/api/overview/zones/{zone.id}").json()["sections"]

    assert section["values"] == {"households": None, "assisted": None}
    assert (section["suppressed"], section["threshold"]) == (True, 5)
    _sign_in(client, "carla")
    [section] = client.get(f"/api/overview/zones/{zone.id}").json()["sections"]
    assert section["values"] == {"households": 3, "assisted": 0}


def test_moving_a_household_does_not_answer_with_more_than_its_place(client, municipality):
    household = make_household(municipality)
    _sign_in(client, "carla")

    response = client.put(
        f"{HOUSEHOLDS}/{household.id}/location", json={"location": point(0.5, 0.5)}
    )

    assert json.loads(response.text) == {
        "location": point(0.5, 0.5),
        "kinds": ["Point"],
        "zones": [],
    }
    with admin_session() as session:
        assert session.get(type(household), household.id).location == point(0.5, 0.5)


def test_amounts_next_to_a_hidden_count_are_hidden_wherever_they_come(
    client, municipality, monkeypatch
):
    """Whatever the order of the figures: an amount says almost as much as the count."""
    from gobernar360.dashboards.social import geography
    from gobernar360.dashboards.social.models import Household
    from gobernar360.platform.geo.contract import ZoneMetric

    counts = geography.households.metrics
    amount = ZoneMetric("spent", lambda today, filters: func.count(Household.id) * 10, "money")
    _neighbourhoods(municipality, Sur=6, Norte=2, Oeste=4)
    _sign_in(client)

    for metrics in ((amount, counts[0]), (counts[0], amount)):
        record = dataclasses.replace(geography.households, metrics=metrics)
        module = dataclasses.replace(registry.get_module("social"), located=(record,))
        monkeypatch.setitem(registry._modules, "social", module)

        body = client.get(f"{HOUSEHOLDS}/zones").json()

        assert {row["zone"]["name"]: row["values"]["spent"] for row in body["zones"]} == {
            "Norte": None,
            "Oeste": None,
            "Sur": "60.00",
        }
        assert _counts(client) == {"Norte": None, "Oeste": None, "Sur": 6}
