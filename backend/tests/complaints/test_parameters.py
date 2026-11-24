"""Areas, zones, types and the working calendar."""

import pytest

from tests.complaints.factories import (
    BASE,
    Setup,
    at,
    complaints_member,
    make_area,
    make_holiday,
    make_type,
    make_zone,
    pin_clock,
    signed_in,
)


def _names(response):
    assert response.status_code == 200, response.text
    return [item["name"] for item in response.json()]


@pytest.mark.parametrize("path", ["areas", "zones"])
def test_admin_manages_named_catalogs(client, path):
    signed_in(client, "admin")

    created = client.post(f"{BASE}/{path}", json={"name": "  Norte "})
    assert created.status_code == 201, created.text
    assert created.json() == {"id": created.json()["id"], "name": "Norte"}
    item_id = created.json()["id"]
    client.post(f"{BASE}/{path}", json={"name": "Centro"})

    renamed = client.patch(f"{BASE}/{path}/{item_id}", json={"name": "Barrio Norte"})
    assert renamed.json()["name"] == "Barrio Norte"
    assert _names(client.get(f"{BASE}/{path}")) == ["Barrio Norte", "Centro"]
    assert client.delete(f"{BASE}/{path}/{item_id}").status_code == 204
    assert _names(client.get(f"{BASE}/{path}")) == ["Centro"]


def test_admin_manages_types(client):
    municipality = signed_in(client, "admin")
    lights, works = make_area(municipality, "Alumbrado"), make_area(municipality, "Obras")

    created = client.post(
        f"{BASE}/types",
        json={"name": "Luminaria apagada", "area_id": str(lights.id), "target_days": 3},
    )
    assert created.status_code == 201, created.text
    type_id = created.json()["id"]
    assert created.json() == {
        "id": type_id,
        "name": "Luminaria apagada",
        "area": {"id": str(lights.id), "name": "Alumbrado"},
        "target_days": 3,
        "is_active": True,
    }

    changed = client.patch(
        f"{BASE}/types/{type_id}",
        json={"area_id": str(works.id), "target_days": 7, "is_active": False},
    ).json()

    assert (changed["area"]["name"], changed["target_days"], changed["is_active"]) == (
        "Obras",
        7,
        False,
    )
    assert client.delete(f"{BASE}/types/{type_id}").status_code == 204
    assert client.get(f"{BASE}/types").json() == []


@pytest.mark.parametrize("target_days", [0, 366, None])
def test_a_type_needs_a_sensible_target(client, target_days):
    municipality = signed_in(client, "admin")
    area = make_area(municipality)

    response = client.post(
        f"{BASE}/types", json={"name": "x", "area_id": str(area.id), "target_days": target_days}
    )

    assert response.status_code == 422


def test_a_new_target_does_not_rewrite_existing_complaints(client):
    setup = Setup(signed_in(client, "admin"), target_days=5)
    complaint = setup.complaint("assigned")

    client.patch(f"{BASE}/types/{setup.type.id}", json={"target_days": 20})

    clock = client.get(f"{BASE}/complaints/{complaint.id}").json()["clock"]
    assert clock["target_days"] == 5


def test_catalogs_in_use_are_not_deleted(client):
    setup = Setup(signed_in(client, "admin"))
    setup.complaint()
    unused = make_area(setup.municipality, "Sin uso")

    for path in (
        f"areas/{setup.area.id}",
        f"zones/{setup.zone.id}",
        f"types/{setup.type.id}",
    ):
        response = client.delete(f"{BASE}/{path}")
        assert response.status_code == 409, path
        assert response.json()["error"]["code"] == "in_use"
    assert client.delete(f"{BASE}/areas/{unused.id}").status_code == 204


@pytest.mark.parametrize("level", ["viewer", "editor"])
def test_only_admins_change_the_parameters(client, level):
    setup = Setup(signed_in(client, level))
    holiday = make_holiday(setup.municipality, at(24).date())

    attempts = [
        client.post(f"{BASE}/areas", json={"name": "x"}),
        client.patch(f"{BASE}/areas/{setup.area.id}", json={"name": "x"}),
        client.delete(f"{BASE}/zones/{setup.zone.id}"),
        client.post(
            f"{BASE}/types",
            json={"name": "x", "area_id": str(setup.area.id), "target_days": 1},
        ),
        client.patch(f"{BASE}/types/{setup.type.id}", json={"target_days": 1}),
        client.put(f"{BASE}/calendar/weekdays", json={"weekdays": [1]}),
        client.post(f"{BASE}/calendar/holidays", json={"date": "2026-05-01", "name": "x"}),
        client.delete(f"{BASE}/calendar/holidays/{holiday.id}"),
    ]

    assert [response.status_code for response in attempts] == [403] * len(attempts)
    assert _names(client.get(f"{BASE}/types")) == [setup.type.name]
    assert client.get(f"{BASE}/calendar").json()["weekdays"] == [1, 2, 3, 4, 5]


def test_the_calendar_defaults_to_monday_to_friday_without_holidays(client):
    signed_in(client, "viewer")

    assert client.get(f"{BASE}/calendar").json() == {"weekdays": [1, 2, 3, 4, 5], "holidays": []}


def test_admin_sets_working_days_and_holidays_and_the_clock_follows(client):
    setup = Setup(signed_in(client, "admin"), target_days=5)
    complaint = setup.complaint("assigned", received_at=at(2))
    pin_clock(client, at(9))
    path = f"{BASE}/complaints/{complaint.id}"
    assert client.get(path).json()["clock"]["used_days"] == 5

    saturdays = client.put(f"{BASE}/calendar/weekdays", json={"weekdays": [6, 1, 2, 3, 4, 5, 1]})
    holiday = client.post(
        f"{BASE}/calendar/holidays", json={"date": "2026-03-04", "name": "Día del pueblo"}
    )

    assert saturdays.json()["weekdays"] == [1, 2, 3, 4, 5, 6]
    assert holiday.status_code == 201, holiday.text
    assert client.get(f"{BASE}/calendar").json()["holidays"] == [
        {"id": holiday.json()["id"], "date": "2026-03-04", "name": "Día del pueblo"}
    ]
    # Tuesday 3, Thursday 5, Friday 6, Saturday 7 and Monday 9.
    assert client.get(path).json()["clock"]["used_days"] == 5
    duplicate = client.post(f"{BASE}/calendar/holidays", json={"date": "2026-03-04", "name": "x"})
    assert duplicate.status_code == 409
    assert client.delete(f"{BASE}/calendar/holidays/{holiday.json()['id']}").status_code == 204
    assert client.get(path).json()["clock"]["used_days"] == 6


@pytest.mark.parametrize("weekdays", [[], [0], [8]])
def test_working_days_must_be_weekdays(client, weekdays):
    signed_in(client, "admin")

    assert client.put(f"{BASE}/calendar/weekdays", json={"weekdays": weekdays}).status_code == 422


def test_another_municipalitys_catalogs_are_invisible_and_untouchable(client):
    other = complaints_member("admin", email="x@saira.test", municipality_name="Saira")
    their_area, their_zone = make_area(other, "Ajena"), make_zone(other, "Ajena")
    their_type = make_type(other, their_area, "Ajeno")
    their_holiday = make_holiday(other, at(24).date())
    signed_in(client, "admin")

    for path in ("areas", "zones", "types"):
        assert client.get(f"{BASE}/{path}").json() == [], path
    assert client.get(f"{BASE}/calendar").json()["holidays"] == []
    attempts = [
        client.patch(f"{BASE}/areas/{their_area.id}", json={"name": "x"}),
        client.delete(f"{BASE}/zones/{their_zone.id}"),
        client.patch(f"{BASE}/types/{their_type.id}", json={"target_days": 1}),
        client.delete(f"{BASE}/types/{their_type.id}"),
        client.delete(f"{BASE}/calendar/holidays/{their_holiday.id}"),
    ]
    assert [response.status_code for response in attempts] == [404] * len(attempts)
