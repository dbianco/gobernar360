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
        is_free=False,
        cost=1500,
        duration_days=7,
        annual_volume=300,
    )
    link_requirement(procedure, make_requirement(municipality))
    make_procedure(municipality, area, "Baja", is_active=False)

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
        ],
        ["Baja", "Rentas", "both", "in_person", "", "yes", "", "", "", "no", "0"],
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
