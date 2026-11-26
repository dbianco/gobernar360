"""Sign-in with CiDi and procedures that can be done entirely from home."""

import csv
import io
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from gobernar360.core.db import tenant_session
from gobernar360.dashboards.procedures import module, report
from gobernar360.platform.access import system_context
from gobernar360.platform.clock import get_today
from gobernar360.platform.models import MonthlyReport
from tests.factories import (
    admin_session,
    current_overview,
    login,
    make_membership,
    make_municipality,
    make_user,
)
from tests.procedures.factories import (
    BASE,
    link_requirement,
    make_area,
    make_procedure,
    make_requirement,
    procedures_member,
    signed_in,
)

URL = f"{BASE}/procedures"
WEB = "https://noetinger.example/t"


def _error(response) -> tuple[int, dict]:
    return response.status_code, response.json()["error"]


def _summary(client) -> dict:
    return client.get(f"{BASE}/summary").json()


def _detail(client, procedure) -> dict:
    return client.get(f"{URL}/{procedure.id}").json()


IN_PERSON_ERROR = (
    422,
    {
        "code": "cidi_level_in_person",
        "message": "A procedure done only in person has no CiDi level.",
    },
)


# The level


@pytest.mark.parametrize("channel", ["online", "both"])
@pytest.mark.parametrize("level", [1, 2, 3, None])
def test_what_is_done_online_may_ask_for_a_level(client, channel, level):
    area = make_area(signed_in(client))

    created = client.post(
        URL,
        json={"name": "X", "area_id": str(area.id), "channel": channel, "cidi_level": level},
    )

    assert (created.status_code, created.json()["cidi_level"]) == (201, level)


@pytest.mark.parametrize("level", [0, 4, -1, "2", True, 1.5])
def test_other_levels_do_not_exist(client, level):
    municipality = signed_in(client)
    area = make_area(municipality)
    procedure = make_procedure(municipality, area, channel="online")
    body = {"name": "X", "area_id": str(area.id), "channel": "online", "cidi_level": level}

    for refused in (
        client.post(URL, json=body),
        client.patch(f"{URL}/{procedure.id}", json={"cidi_level": level}),
    ):
        status, error = _error(refused)
        assert (status, error["code"]) == (422, "validation_error")
        assert [problem["field"] for problem in error["details"]] == ["cidi_level"]


def test_what_is_only_done_in_person_has_no_level(client):
    municipality = signed_in(client)
    area = make_area(municipality)
    office = make_procedure(municipality, area, "Mostrador")
    body = {"name": "X", "area_id": str(area.id), "channel": "in_person", "cidi_level": 1}

    assert _error(client.post(URL, json=body)) == IN_PERSON_ERROR
    # In person is what a procedure is unless told otherwise.
    del body["channel"]
    assert _error(client.post(URL, json=body)) == IN_PERSON_ERROR
    assert _error(client.patch(f"{URL}/{office.id}", json={"cidi_level": 3})) == IN_PERSON_ERROR
    both_at_once = {"channel": "in_person", "cidi_level": 3}
    assert _error(client.patch(f"{URL}/{office.id}", json=both_at_once)) == IN_PERSON_ERROR
    assert client.get(URL).json()["total"] == 1


@pytest.mark.parametrize(
    "fields",
    [
        {"channel": "in_person", "cidi_level": 1},
        {"channel": "online", "cidi_level": 0},
        {"channel": "online", "cidi_level": 4},
    ],
)
def test_the_database_has_the_last_word(fields):
    municipality = make_municipality()
    area = make_area(municipality)

    with pytest.raises(IntegrityError):
        make_procedure(municipality, area, **fields)


def test_a_level_is_set_changed_and_taken_away(client):
    procedure = make_procedure(signed_in(client), channel="both")
    path = f"{URL}/{procedure.id}"

    for level in (2, 3, None):
        assert client.patch(path, json={"cidi_level": level}).json()["cidi_level"] == level
    client.patch(path, json={"cidi_level": 1})
    assert client.patch(path, json={"name": "Otro nombre"}).json()["cidi_level"] == 1


def test_what_stops_being_online_loses_its_level(client):
    procedure = make_procedure(signed_in(client), channel="both", cidi_level=2)
    path = f"{URL}/{procedure.id}"

    # Still online: the level stays.
    assert client.patch(path, json={"channel": "online"}).json()["cidi_level"] == 2
    assert client.patch(path, json={"channel": "in_person"}).json()["cidi_level"] is None
    assert client.patch(path, json={"channel": "both"}).json()["cidi_level"] is None
    together = client.patch(path, json={"channel": "in_person", "cidi_level": None})
    assert together.status_code == 200


def test_viewers_do_not_change_it(client):
    procedure = make_procedure(signed_in(client, "viewer"), channel="online")

    assert _error(client.patch(f"{URL}/{procedure.id}", json={"cidi_level": 1}))[0] == 403


def test_the_list_is_narrowed_by_level(client):
    municipality = signed_in(client, "viewer")
    area = make_area(municipality)
    for name, channel, level in (
        ("Uno", "online", 1),
        ("Dos", "both", 2),
        ("Dos bis", "online", 2),
        ("Ninguno", "online", None),
        ("Mostrador", "in_person", None),
    ):
        make_procedure(municipality, area, name, channel=channel, cidi_level=level)

    def names(level):
        page = client.get(URL, params={"cidi_level": level} if level else {}).json()
        return [item["name"] for item in page["items"]], page["total"]

    assert names("1") == (["Uno"], 1)
    assert names("2") == (["Dos", "Dos bis"], 2)
    assert names("3") == ([], 0)
    assert names("none") == (["Mostrador", "Ninguno"], 2)
    assert names(None)[1] == 5
    assert client.get(URL, params={"cidi_level": "4"}).status_code == 422


def test_the_file_has_the_level(client):
    municipality = signed_in(client, "viewer")
    area = make_area(municipality)
    make_procedure(municipality, area, "A", channel="online", cidi_level=3)
    make_procedure(municipality, area, "B", channel="online")

    text = client.get(f"{BASE}/export/procedures.csv").content.decode("utf-8-sig")

    rows = list(csv.DictReader(io.StringIO(text)))
    assert [(row["name"], row["cidi_level"]) for row in rows] == [("A", "3"), ("B", "")]


# Fully digital


def _with(municipality, *asks, **fields):
    """A procedure that is online with an address, and asks for that: (mandatory, format)."""
    defaults = {"channel": "online", "url": WEB}
    procedure = make_procedure(municipality, **(defaults | fields))
    for number, (mandatory, how) in enumerate(asks):
        requirement = make_requirement(municipality, f"Requisito {procedure.id} {number}")
        link_requirement(procedure, requirement, mandatory=mandatory, format=how)
    return procedure


@pytest.mark.parametrize(
    ("fields", "asks", "digital"),
    [
        ({}, [], True),
        ({}, [(True, "digital"), (False, "digital")], True),
        ({"channel": "both"}, [(True, "digital")], True),
        # What is optional may be left out.
        ({}, [(False, "paper")], True),
        ({}, [(True, "paper")], False),
        ({}, [(True, "digital"), (True, "paper")], False),
        ({"url": ""}, [], False),
        ({"channel": "both", "url": ""}, [], False),
        ({"channel": "in_person"}, [], False),
        ({"is_active": False}, [], False),
        # Signing in with CiDi has nothing to do with it.
        ({"cidi_level": 3}, [(True, "paper")], False),
    ],
)
def test_when_a_procedure_is_fully_digital(client, fields, asks, digital):
    procedure = _with(signed_in(client, "viewer"), *asks, **fields)

    assert _detail(client, procedure)["fully_digital"] is digital
    [listed] = client.get(URL).json()["items"]
    assert listed["fully_digital"] is digital
    assert _summary(client)["digital"] == int(digital)


def test_the_paper_of_one_procedure_is_not_that_of_another(client):
    municipality = signed_in(client, "viewer")
    _with(municipality, (True, "paper"), name="Con papel")
    _with(municipality, name="Sin papel")

    digital = {p["name"]: p["fully_digital"] for p in client.get(URL).json()["items"]}

    assert digital == {"Con papel": False, "Sin papel": True}


def test_a_paper_requirement_takes_it_away_and_making_it_optional_gives_it_back(client):
    municipality = signed_in(client)
    procedure = _with(municipality)
    requirement = make_requirement(municipality)
    path = f"{URL}/{procedure.id}/requirements"

    link = client.post(path, json={"requirement_id": str(requirement.id)}).json()
    assert (_detail(client, procedure)["fully_digital"], _summary(client)["digital"]) == (False, 0)
    client.patch(f"{path}/{link['id']}", json={"mandatory": False})
    assert (_detail(client, procedure)["fully_digital"], _summary(client)["digital"]) == (True, 1)


def test_nobody_types_it(client):
    municipality = signed_in(client)
    procedure = _with(municipality, (True, "paper"))

    refused = client.patch(f"{URL}/{procedure.id}", json={"fully_digital": True})

    assert refused.status_code == 422


# Figures


def _figures(client) -> dict:
    keys = ("procedures", "online", "cidi", "cidi_ratio", "digital", "digital_ratio")
    summary = _summary(client)
    return {key: summary[key] for key in keys}


def test_the_figures_of_a_known_inventory(client):
    municipality = signed_in(client, "viewer")
    _with(municipality, name="A", cidi_level=1)
    _with(municipality, name="B", cidi_level=2, channel="both")
    _with(municipality, (True, "paper"), name="C", cidi_level=2)
    _with(municipality, name="D")
    _with(municipality, name="E", channel="in_person", url="")
    # No longer offered: counts nowhere.
    _with(municipality, name="F", cidi_level=3, is_active=False)

    assert _figures(client) == {
        "procedures": 5,
        "online": 4,
        "cidi": 3,
        "cidi_ratio": 0.75,
        "digital": 3,
        "digital_ratio": 0.6,
    }
    assert _summary(client)["by_cidi_level"] == [
        {"level": 1, "count": 1},
        {"level": 2, "count": 2},
        {"level": 3, "count": 0},
        {"level": None, "count": 2},
    ]
    [section] = current_overview(client.get("/api/overview").json())
    indicators = {i["key"]: (i["value"], i["unit"]) for i in section["indicators"]}
    assert indicators == {
        "procedures.active": (5, None),
        "procedures.online": (4, None),
        "procedures.online_ratio": (0.8, "ratio"),
        "procedures.cidi": (3, None),
        "procedures.cidi_ratio": (0.75, "ratio"),
        "procedures.digital": (3, None),
        "procedures.digital_ratio": (0.6, "ratio"),
        "procedures.requirements": (1, None),
        "procedures.sources": (0, None),
    }


def test_without_online_procedures_there_is_no_share_of_them(client):
    make_procedure(signed_in(client, "viewer"))

    assert _figures(client) == {
        "procedures": 1,
        "online": 0,
        "cidi": 0,
        "cidi_ratio": None,
        "digital": 0,
        "digital_ratio": 0.0,
    }


def test_the_indicators_are_in_the_catalogue_and_can_be_published():
    catalogue = {definition.key: definition for definition in module.indicators}

    for key, unit, name in (
        ("procedures.cidi", None, "Trámites con ingreso por CiDi"),
        (
            "procedures.cidi_ratio",
            "ratio",
            "Proporción de trámites en línea que usan CiDi",
        ),
        ("procedures.digital", None, "Trámites 100 % digitales"),
        ("procedures.digital_ratio", "ratio", "Proporción de trámites 100 % digitales"),
    ):
        definition = catalogue[key]
        assert (definition.unit, definition.name, definition.aggregate) == (unit, name, True)
        assert definition.higher_is_better and not definition.reconstructible


def test_the_summary_gives_exactly_the_indicators_of_the_catalogue(client):
    municipality = signed_in(client, "viewer")
    make_procedure(municipality)

    with tenant_session(municipality.id) as db:
        given = module.get_summary(system_context(db, municipality.id), date(2026, 11, 26))

    assert [(i.key, i.unit) for i in given] == [(d.key, d.unit) for d in module.indicators]


def test_another_municipalitys_procedures_do_not_count(client):
    municipality = signed_in(client, "viewer")
    _with(municipality, name="Propio", cidi_level=1)
    saira = procedures_member("viewer", "leo@saira.test", municipality_name="Saira")
    _with(saira, name="Ajeno", cidi_level=2)
    _with(saira, (True, "paper"), name="Ajeno con papel")

    assert _figures(client) == {
        "procedures": 1,
        "online": 1,
        "cidi": 1,
        "cidi_ratio": 1.0,
        "digital": 1,
        "digital_ratio": 1.0,
    }
    client.post("/api/auth/logout")
    login(client, "leo@saira.test")
    assert (_figures(client)["cidi"], _figures(client)["cidi_ratio"]) == (1, 0.5)
    assert [item["name"] for item in client.get(URL).json()["items"]] == [
        "Ajeno",
        "Ajeno con papel",
    ]


# The monthly report


def _tables(municipality):
    with tenant_session(municipality.id) as db:
        return report.report_tables(
            system_context(db, municipality.id), date(2026, 10, 1), date(2026, 10, 31)
        )


def test_the_report_has_the_levels_in_counts_and_no_text_people_typed():
    municipality = make_municipality()
    area = make_area(municipality, "Área <secreta>")
    for name, level in (("Trámite secreto", 2), ("Otro secreto", None)):
        make_procedure(municipality, area, name, channel="online", cidi_level=level)

    [table] = _tables(municipality)

    assert (table.key, table.title) == (
        "procedures.cidi_levels",
        "Trámites por nivel de CiDi, al cerrar el informe",
    )
    assert [(column.title, column.kind) for column in table.columns] == [
        ("Nivel de CiDi", "text"),
        ("Trámites vigentes", "number"),
    ]
    assert table.rows == [
        ("Nivel 1 – Confirmado", 0),
        ("Nivel 2 – Verificado", 1),
        ("Nivel 3 – Autenticado", 0),
        ("Sin CiDi", 1),
    ]


def test_a_report_without_procedures_has_no_table():
    municipality = make_municipality()
    make_procedure(municipality, is_active=False)

    assert _tables(municipality) == []


def test_closing_a_month_freezes_the_table(client):
    client.app.dependency_overrides[get_today] = lambda: date(2026, 11, 10)
    municipality = make_municipality()
    make_membership(
        make_user("admin@noetinger.test"), municipality, admin=True, enable=["procedures"]
    )
    procedure = make_procedure(municipality, channel="online", cidi_level=1)
    login(client, "admin@noetinger.test")

    closed = client.post("/api/reports/2026/10/close", json={"comments": {}})
    client.patch(f"{URL}/{procedure.id}", json={"cidi_level": None})

    assert closed.status_code == 201, closed.text
    with admin_session() as session:
        content = session.scalars(select(MonthlyReport)).one().content
    [dashboard] = content["dashboards"]
    [table] = dashboard["tables"]
    assert table["rows"][0] == ["Nivel 1 – Confirmado", 1]
