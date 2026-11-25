"""Figures by name: things that share a name stay apart, and ties come by name."""

from datetime import date

import pytest

from gobernar360.platform.clock import get_today
from tests.economic.factories import (
    economic_member,
    make_actor,
    make_actor_type,
    make_assignment,
    make_sector,
    make_tool,
    make_tool_category,
)
from tests.factories import login
from tests.procedures.factories import (
    link_requirement,
    make_area,
    make_procedure,
    make_requirement,
    make_source,
    procedures_member,
)
from tests.social.factories import (
    make_benefit,
    make_benefit_category,
    make_delivery,
    make_household,
    make_intervention,
    make_intervention_type,
    make_social_person,
    social_member,
)

EMAIL = "ana@noetinger.test"


@pytest.fixture(autouse=True)
def pinned_today(client):
    client.app.dependency_overrides[get_today] = lambda: date(2026, 6, 15)


def test_benefits_and_interventions(client):
    municipality = social_member("viewer")
    food = make_benefit_category(municipality, "Alimentos")
    person = make_social_person(municipality)
    names = ("Leche", "Caja", "Caja", "Zapatos")
    for name in names:
        make_delivery(municipality, make_benefit(municipality, food, name), person, quantity=2)
    kinds = [make_intervention_type(municipality, n) for n in ("Visita", "Llamado", "Llamado")]
    for kind in kinds:
        make_intervention(municipality, kind, person)
    login(client, EMAIL)

    summary = client.get("/api/dashboards/social/summary").json()

    assert [(row["benefit"], row["deliveries"], row["units"]) for row in summary["benefits"]] == [
        ("Caja", 1, 2),
        ("Caja", 1, 2),
        ("Leche", 1, 2),
        ("Zapatos", 1, 2),
    ]
    assert [(row["name"], row["count"]) for row in summary["intervention_types"]] == [
        ("Llamado", 1),
        ("Llamado", 1),
        ("Visita", 1),
    ]


def test_tools_and_sectors(client):
    municipality = economic_member("viewer")
    category = make_tool_category(municipality)
    actor = make_actor(municipality)
    for name in ("Feria", "Curso", "Curso"):
        make_assignment(municipality, make_tool(municipality, category, name), actor=actor)
    for name in ("Textil", "Agro", "Agro"):
        make_actor(municipality, sector_id=make_sector(municipality, name).id)
        make_actor(municipality, actor_type_id=make_actor_type(municipality, name).id)
    login(client, EMAIL)

    summary = client.get("/api/dashboards/economic/summary").json()
    reports = client.get("/api/dashboards/economic/reports").json()

    assert [(row["tool"], row["count"]) for row in summary["actor_tools"]] == [
        ("Curso", 1),
        ("Curso", 1),
        ("Feria", 1),
    ]
    for report in ("actors_by_sector", "actors_by_type"):
        assert [(row["name"], row["count"]) for row in reports[report]] == [
            (None, 4),
            ("Agro", 1),
            ("Agro", 1),
            ("Textil", 1),
        ], report


def test_procedures(client):
    municipality = procedures_member("viewer")
    areas = [make_area(municipality, name) for name in ("Tránsito", "Obras", "Obras")]
    requirement = make_requirement(municipality, "DNI", make_source(municipality))
    for area in areas:
        link_requirement(make_procedure(municipality, area, "Trámite"), requirement)
    login(client, EMAIL)

    summary = client.get("/api/dashboards/procedures/summary").json()

    assert [(row["name"], row["count"]) for row in summary["by_area"]] == [
        ("Obras", 1),
        ("Obras", 1),
        ("Tránsito", 1),
    ]


def test_members_of_a_household_come_head_first_and_then_by_name(client):
    municipality = social_member("viewer")
    household = make_household(municipality)
    for first, last, relationship in (
        *((name, "Gomez", "child") for name in ("Ivo", "Bruno", "Eva", "Ana")),
        ("Zoe", "Zapata", "head"),
        ("Carla", "Alvarez", "partner"),
    ):
        make_social_person(
            municipality, first, last, household=household, relationship=relationship
        )
    login(client, EMAIL)

    detail = client.get(f"/api/dashboards/social/households/{household.id}").json()

    assert [member["full_name"] for member in detail["members"]] == [
        "Zapata, Zoe",
        "Alvarez, Carla",
        *(f"Gomez, {name}" for name in ("Ana", "Bruno", "Eva", "Ivo")),
    ]
    assert detail["head"]["full_name"] == "Zapata, Zoe"


def test_people_of_the_file_come_by_last_and_first_name(client):
    municipality = social_member("viewer")
    firsts = ["Zoe", "Eva", "Ana", "Iris", "Hugo", "Bruno"]
    for first, last in [*((name, "Gomez") for name in firsts), ("Luis", "Alvarez")]:
        make_social_person(municipality, first, last)
    login(client, EMAIL)

    lines = client.get("/api/dashboards/social/export/people.csv").text.splitlines()[1:]

    assert [line.split(",")[:2] for line in lines] == [
        ["Alvarez", "Luis"],
        *(["Gomez", name] for name in sorted(firsts)),
    ]


def test_people_of_the_file_who_share_a_name_always_come_in_the_same_order(client):
    municipality = social_member("viewer")
    documents = {}
    for number in range(8):
        dni = str(20000000 + number)
        documents[make_social_person(municipality, "Ana", "Gomez", dni=dni).id] = dni
    login(client, EMAIL)

    lines = client.get("/api/dashboards/social/export/people.csv").text.splitlines()[1:]

    assert [line.split(",")[2] for line in lines] == [
        documents[key] for key in sorted(documents, key=str)
    ]
