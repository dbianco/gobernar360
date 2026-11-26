import pytest

from tests.factories import current_overview, make_municipality
from tests.procedures.factories import (
    BASE,
    link_requirement,
    make_area,
    make_procedure,
    make_requirement,
    make_source,
    signed_in,
)


def known_data(municipality):
    """Four active procedures and an inactive one, sharing requirements and sources."""
    rentas, obras = make_area(municipality, "Rentas"), make_area(municipality, "Obras")
    rentas_source = make_source(municipality, "Rentas municipal", "municipal", rentas)
    catastro = make_source(municipality, "Catastro municipal", "municipal")
    registry = make_source(municipality, "Registro Civil", "provincial")
    make_source(municipality, "ARCA", "national")  # Never asked for.
    free_debt = make_requirement(municipality, "Libre deuda", rentas_source)
    tax_id = make_requirement(municipality, "Constancia de tasa", rentas_source)
    plan = make_requirement(municipality, "Plano", catastro)
    birth = make_requirement(municipality, "Partida de nacimiento", registry)
    dni = make_requirement(municipality, "DNI")
    make_requirement(municipality, "Sin uso")

    shop = make_procedure(municipality, rentas, "Habilitación", channel="both", annual_volume=100)
    works = make_procedure(municipality, obras, "Permiso de obra", annual_volume=40)
    licence = make_procedure(municipality, rentas, "Licencia", channel="online", annual_volume=300)
    empty = make_procedure(municipality, obras, "Consulta")
    old = make_procedure(municipality, obras, "Viejo", is_active=False, annual_volume=9000)
    for procedure, requirements in (
        # Two requirements of the same source: the procedure counts once for it.
        (shop, (free_debt, tax_id, dni)),
        (works, (free_debt, plan, dni)),
        (licence, (birth, dni)),
        (old, (free_debt, plan, birth, dni)),
    ):
        for requirement in requirements:
            link_requirement(procedure, requirement)
    return empty


def test_summary_counts_only_active_procedures(client):
    known_data(signed_in(client, "viewer"))

    response = client.get(f"{BASE}/summary")

    assert response.status_code == 200
    assert response.json() == {
        "procedures": 4,
        "online": 2,
        "cidi": 0,
        "cidi_ratio": 0.0,
        "digital": 0,
        "digital_ratio": 0.0,
        "average_requirements": 2.0,
        "requirements": 6,
        "sources": 4,
        "by_area": [{"name": "Obras", "count": 2}, {"name": "Rentas", "count": 2}],
        "by_channel": [
            {"channel": "in_person", "count": 2},
            {"channel": "online", "count": 1},
            {"channel": "both", "count": 1},
        ],
        "by_cidi_level": [
            {"level": 1, "count": 0},
            {"level": 2, "count": 0},
            {"level": 3, "count": 0},
            {"level": None, "count": 4},
        ],
        "top_requirements": [
            {"name": "DNI", "source": None, "count": 3},
            {"name": "Libre deuda", "source": "Rentas municipal", "count": 2},
            {"name": "Constancia de tasa", "source": "Rentas municipal", "count": 1},
            {"name": "Partida de nacimiento", "source": "Registro Civil", "count": 1},
            {"name": "Plano", "source": "Catastro municipal", "count": 1},
        ],
    }


def test_summary_of_an_empty_dashboard(client):
    signed_in(client, "viewer")

    assert client.get(f"{BASE}/summary").json() == {
        "procedures": 0,
        "online": 0,
        "cidi": 0,
        "cidi_ratio": None,
        "digital": 0,
        "digital_ratio": None,
        "average_requirements": None,
        "requirements": 0,
        "sources": 0,
        "by_area": [],
        "by_channel": [
            {"channel": "in_person", "count": 0},
            {"channel": "online", "count": 0},
            {"channel": "both", "count": 0},
        ],
        "by_cidi_level": [{"level": level, "count": 0} for level in (1, 2, 3, None)],
        "top_requirements": [],
    }


def test_top_requirements_stop_at_ten(client):
    municipality = signed_in(client, "viewer")
    procedure = make_procedure(municipality)
    for number in range(12):
        link_requirement(procedure, make_requirement(municipality, f"Requisito {number:02}"))

    top = client.get(f"{BASE}/summary").json()["top_requirements"]

    assert [row["name"] for row in top] == [f"Requisito {number:02}" for number in range(10)]


def test_opportunities_rank_sources_by_level_then_volume(client):
    known_data(signed_in(client, "viewer"))

    response = client.get(f"{BASE}/opportunities")

    assert response.status_code == 200
    body = response.json()
    assert [
        (
            row["source"]["name"],
            row["source"]["level"],
            row["requirements"],
            row["procedures"],
            row["annual_volume"],
        )
        for row in body["sources"]
    ] == [
        ("Rentas municipal", "municipal", 2, 2, 140),
        ("Catastro municipal", "municipal", 1, 1, 40),
        ("Registro Civil", "provincial", 1, 1, 300),
    ]
    assert body["sources"][0]["source"]["area"]["name"] == "Rentas"
    assert body["without_source"] == {"requirements": 1, "procedures": 3, "annual_volume": 440}


def test_opportunities_treat_an_unknown_volume_as_zero(client):
    municipality = signed_in(client, "viewer")
    source = make_source(municipality)
    link_requirement(make_procedure(municipality), make_requirement(municipality, source=source))

    body = client.get(f"{BASE}/opportunities").json()

    assert [(row["procedures"], row["annual_volume"]) for row in body["sources"]] == [(1, 0)]
    assert body["without_source"] == {"requirements": 0, "procedures": 0, "annual_volume": 0}


def test_summary_and_opportunities_need_access_and_stay_inside_the_municipality(client):
    known_data(make_municipality("Saira"))
    signed_in(client, "viewer")

    assert client.get(f"{BASE}/summary").json()["procedures"] == 0
    assert client.get(f"{BASE}/opportunities").json()["sources"] == []


def test_member_without_access_gets_nothing(client):
    signed_in(client, None)

    for path in ("summary", "opportunities", "export/procedures.csv"):
        assert client.get(f"{BASE}/{path}").status_code == 403
    assert client.get("/api/overview").json() == []


def test_overview_shows_the_procedures_indicators(client):
    known_data(signed_in(client, "viewer"))

    assert current_overview(client.get("/api/overview").json()) == [
        {
            "dashboard_key": "procedures",
            "indicators": [
                {"key": "procedures.active", "value": 4, "unit": None},
                {"key": "procedures.online", "value": 2, "unit": None},
                {"key": "procedures.online_ratio", "value": 0.5, "unit": "ratio"},
                {"key": "procedures.cidi", "value": 0, "unit": None},
                {"key": "procedures.cidi_ratio", "value": 0.0, "unit": "ratio"},
                {"key": "procedures.digital", "value": 0, "unit": None},
                {"key": "procedures.digital_ratio", "value": 0.0, "unit": "ratio"},
                {"key": "procedures.requirements", "value": 6, "unit": None},
                {"key": "procedures.sources", "value": 4, "unit": None},
            ],
            "status": [],
        }
    ]


def test_overview_of_an_empty_procedures_dashboard_has_no_indicators(client):
    signed_in(client, "viewer")

    assert client.get("/api/overview").json() == [
        {"dashboard_key": "procedures", "indicators": [], "status": []}
    ]


def test_areas_with_more_procedures_come_first_and_the_average_has_one_decimal(client):
    municipality = signed_in(client, "viewer")
    obras, rentas = make_area(municipality, "Obras"), make_area(municipality, "Rentas")
    requirements = [make_requirement(municipality, f"Requisito {n}") for n in range(3)]
    make_procedure(municipality, obras, "Permiso")
    for name, asks in (("Habilitación", 3), ("Licencia", 2), ("Tasa", 2)):
        procedure = make_procedure(municipality, rentas, name)
        for requirement in requirements[:asks]:
            link_requirement(procedure, requirement)

    summary = client.get(f"{BASE}/summary").json()

    assert summary["by_area"] == [{"name": "Rentas", "count": 3}, {"name": "Obras", "count": 1}]
    # 7 requirements asked by 4 procedures.
    assert summary["average_requirements"] == 1.8


def test_procedures_that_ask_for_nothing_average_zero_requirements(client):
    municipality = signed_in(client, "viewer")
    make_procedure(municipality, make_area(municipality, "Obras"), "Consulta")

    summary = client.get(f"{BASE}/summary").json()

    assert (summary["procedures"], summary["average_requirements"]) == (1, 0.0)
    assert summary["top_requirements"] == []


def test_of_two_sources_that_reach_the_same_volume_the_one_in_more_procedures_comes_first(
    client,
):
    municipality = signed_in(client, "viewer")
    alfa, zeta = make_source(municipality, "Alfa"), make_source(municipality, "Zeta")
    big = make_procedure(municipality, name="Grande", annual_volume=100)
    link_requirement(big, make_requirement(municipality, "De Alfa", alfa))
    for number in (1, 2):
        small = make_procedure(municipality, name=f"Chico {number}", annual_volume=50)
        link_requirement(small, make_requirement(municipality, f"De Zeta {number}", zeta))

    body = client.get(f"{BASE}/opportunities").json()

    assert [row["source"]["name"] for row in body["sources"]] == ["Zeta", "Alfa"]


@pytest.mark.parametrize(
    ("requirements", "sources"),
    [(1, 0), (0, 1)],
)
def test_a_dashboard_with_only_a_catalog_shows_its_indicators(client, requirements, sources):
    municipality = signed_in(client, "viewer")
    for number in range(requirements):
        make_requirement(municipality, f"Requisito {number}")
    for number in range(sources):
        make_source(municipality, f"Fuente {number}")

    [section] = current_overview(client.get("/api/overview").json())

    assert section["indicators"] == [
        {"key": "procedures.active", "value": 0, "unit": None},
        {"key": "procedures.online", "value": 0, "unit": None},
        {"key": "procedures.online_ratio", "value": None, "unit": "ratio"},
        {"key": "procedures.cidi", "value": 0, "unit": None},
        {"key": "procedures.cidi_ratio", "value": None, "unit": "ratio"},
        {"key": "procedures.digital", "value": 0, "unit": None},
        {"key": "procedures.digital_ratio", "value": None, "unit": "ratio"},
        {"key": "procedures.requirements", "value": requirements, "unit": None},
        {"key": "procedures.sources", "value": sources, "unit": None},
    ]
