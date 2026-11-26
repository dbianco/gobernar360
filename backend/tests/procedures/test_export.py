import csv
import io

from tests.procedures.factories import (
    BASE,
    link_requirement,
    make_area,
    make_procedure,
    make_requirement,
    make_source,
    signed_in,
)
from tests.procedures.test_summary import known_data


def _rows(response):
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))


def test_procedures_download_lists_every_procedure(client):
    municipality = signed_in(client, "viewer")
    area = make_area(municipality)
    procedure = make_procedure(
        municipality,
        area,
        "=Licencia",
        audience="people",
        channel="both",
        url="https://noetinger.example/l",
        cidi_level=2,
        is_free=False,
        cost=1500,
        duration_days=7,
        annual_volume=300,
    )
    link_requirement(procedure, make_requirement(municipality))
    make_procedure(municipality, area, "Zonificación", is_active=False)

    rows = _rows(client.get(f"{BASE}/export/procedures.csv"))

    assert rows == [
        [
            "name",
            "area",
            "audience",
            "channel",
            "url",
            "free",
            "cost",
            "duration_days",
            "annual_volume",
            "active",
            "requirements",
            "cidi_level",
        ],
        # Text that a spreadsheet would run as a formula is neutralised.
        [
            "'=Licencia",
            "Rentas",
            "people",
            "both",
            "https://noetinger.example/l",
            "no",
            "1500",
            "7",
            "300",
            "yes",
            "1",
            "2",
        ],
        ["Zonificación", "Rentas", "both", "in_person", "", "yes", "", "", "", "no", "0", ""],
    ]
    assert (
        'filename="procedures.csv"'
        in client.get(f"{BASE}/export/procedures.csv").headers["content-disposition"]
    )


def test_requirements_download_has_one_row_per_requirement_asked(client):
    municipality = signed_in(client, "viewer")
    area = make_area(municipality)
    source = make_source(municipality, area=area)
    procedure = make_procedure(municipality, area, "Habilitación")
    link_requirement(
        procedure, make_requirement(municipality, "Libre deuda", source), note="+ sello"
    )
    link_requirement(
        procedure, make_requirement(municipality, "DNI"), mandatory=False, format="digital"
    )

    rows = _rows(client.get(f"{BASE}/export/procedure-requirements.csv"))

    assert rows == [
        [
            "procedure",
            "area",
            "active",
            "requirement",
            "source",
            "source_level",
            "mandatory",
            "format",
            "note",
        ],
        ["Habilitación", "Rentas", "yes", "DNI", "", "", "no", "digital", ""],
        [
            "Habilitación",
            "Rentas",
            "yes",
            "Libre deuda",
            "Rentas municipal",
            "municipal",
            "yes",
            "paper",
            "'+ sello",
        ],
    ]


def test_opportunities_download_matches_the_report(client):
    known_data(signed_in(client, "viewer"))

    rows = _rows(client.get(f"{BASE}/export/opportunities.csv"))

    assert rows == [
        ["source", "level", "area", "requirements", "procedures", "annual_volume"],
        ["Rentas municipal", "municipal", "Rentas", "2", "2", "140"],
        ["Catastro municipal", "municipal", "", "1", "1", "40"],
        ["Registro Civil", "provincial", "", "1", "1", "300"],
        ["", "none", "", "1", "3", "440"],
    ]


def test_opportunities_have_no_last_row_when_everything_asked_has_a_source(client):
    municipality = signed_in(client, "viewer")
    asked = make_requirement(municipality, source=make_source(municipality))
    link_requirement(make_procedure(municipality), asked)

    rows = _rows(client.get(f"{BASE}/export/opportunities.csv"))

    assert [row[:2] for row in rows[1:]] == [["Rentas municipal", "municipal"]]


def test_downloads_are_named_after_what_they_hold(client):
    signed_in(client, "viewer")

    for path, name in (
        ("procedures", "procedures.csv"),
        ("procedure-requirements", "procedure-requirements.csv"),
        ("opportunities", "procedures-opportunities.csv"),
    ):
        response = client.get(f"{BASE}/export/{path}.csv")
        assert response.headers["content-disposition"] == f'attachment; filename="{name}"', path


def test_what_is_asked_comes_by_procedure_and_requirement_ignoring_case_and_accents(client):
    municipality = signed_in(client, "viewer")
    requirements = [make_requirement(municipality, name) for name in ("dni", "Álbum", "boleta")]
    for name in ("poda", "Árboles", "Baldío"):
        procedure = make_procedure(municipality, name=name)
        for requirement in requirements:
            link_requirement(procedure, requirement)

    _, *rows = _rows(client.get(f"{BASE}/export/procedure-requirements.csv"))

    assert [(row[0], row[3]) for row in rows] == [
        (procedure, requirement)
        for procedure in ("Árboles", "Baldío", "poda")
        for requirement in ("Álbum", "boleta", "dni")
    ]


def test_a_procedure_of_no_days_and_no_volume_is_told_from_one_not_known(client):
    municipality = signed_in(client, "viewer")
    make_procedure(municipality, name="Cero", duration_days=0, annual_volume=0)
    make_procedure(municipality, name="Nada")

    header, *rows = _rows(client.get(f"{BASE}/export/procedures.csv"))

    columns = [header.index(c) for c in ("duration_days", "annual_volume")]
    assert {row[0]: [row[c] for c in columns] for row in rows} == {
        "Cero": ["0", "0"],
        "Nada": ["", ""],
    }


def test_opportunities_download_leaves_out_the_rest_when_everything_has_a_source(client):
    municipality = signed_in(client, "viewer")
    requirement = make_requirement(municipality, "Libre deuda", make_source(municipality))
    link_requirement(make_procedure(municipality, annual_volume=10), requirement)

    rows = _rows(client.get(f"{BASE}/export/opportunities.csv"))

    assert rows[1:] == [["Rentas municipal", "municipal", "", "1", "1", "10"]]
