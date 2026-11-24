"""Monthly reports: closing, freezing, reopening and the PDF (`platform/reports*.py`)."""

import io
from datetime import UTC, date, datetime

import pypdf
import pytest
from sqlalchemy import select

from gobernar360.platform.clock import get_today
from gobernar360.platform.models import (
    AuditLog,
    DashboardStatus,
    IndicatorSnapshot,
    IndicatorTarget,
    MonthlyReport,
)
from gobernar360.platform.report_pdf import ReportDocument, render_report
from tests.factories import admin_session, login, make_membership, make_municipality, make_user
from tests.projects.factories import make_axis, make_department, make_project, make_term

TODAY = date(2026, 11, 20)
API = "/api/reports"


@pytest.fixture(autouse=True)
def pinned_today(client):
    client.app.dependency_overrides[get_today] = lambda: TODAY


def add(*rows):
    with admin_session() as session, session.begin():
        session.add_all(rows)


def admin(client, name="Noetinger", email="ana@noetinger.test", enable=("projects",)):
    municipality = make_municipality(name)
    make_membership(make_user(email), municipality, admin=True, enable=list(enable))
    login(client, email)
    return municipality


def october(municipality):
    """Lights, snapshots, a target and milestones of October 2026 in Noetinger."""
    m = municipality.id
    add(
        DashboardStatus(municipality_id=m, dashboard_key="projects", year=2026, month=10,
                        color="red"),
        IndicatorSnapshot(municipality_id=m, dashboard_key="projects",
                          indicator_key="projects.delayed", year=2026, month=10, value=4),
        IndicatorSnapshot(municipality_id=m, dashboard_key="projects",
                          indicator_key="projects.delayed", year=2026, month=9, value=6),
        IndicatorSnapshot(municipality_id=m, dashboard_key="projects",
                          indicator_key="projects.budget_executed_ratio", year=2026, month=10,
                          value=0.455),
        IndicatorTarget(municipality_id=m, dashboard_key="projects",
                        indicator_key="projects.delayed", year=2026, value=3),
    )  # fmt: skip
    term = make_term(municipality, start_year=2025, end_year=2029)
    axis, department = make_axis(municipality, term), make_department(municipality)
    return make_project(
        municipality,
        term,
        axis,
        department,
        name="Plaza central",
        status="in_progress",
        manual_progress=10,
        milestones=[
            (date(2026, 10, 5), date(2026, 10, 9)),  # reached in October
            (date(2026, 10, 20), None),  # overdue at the end of October
            (date(2026, 9, 1), date(2026, 10, 30)),  # reached in October, late
            (date(2026, 11, 10), None),  # not October's business
        ],
    )


def close(client, comments=None, year=2026, month=10):
    return client.post(f"{API}/{year}/{month}/close", json={"comments": comments or {}})


def dashboard(report, key="projects"):
    return next(d for d in report["content"]["dashboards"] if d["key"] == key)


def indicator(report, key):
    return next(i for i in dashboard(report)["indicators"] if i["key"] == key)


def pdf_text(data: bytes) -> str:
    return "\n".join(page.extract_text() for page in pypdf.PdfReader(io.BytesIO(data)).pages)


# Closing


def test_closing_a_month_freezes_its_lights_indicators_targets_and_milestones(client):
    octobre = admin(client)
    october(octobre)

    response = close(client, {"projects": "  Un mes con lluvias.  "})

    assert response.status_code == 201
    report = response.json()
    assert (report["year"], report["month"], report["version"]) == (2026, 10, 1)
    assert report["status"] == "closed"
    assert report["comments"] == {"projects": "Un mes con lluvias."}
    assert report["content"]["municipality"] == {"name": "Noetinger", "kind": "municipality"}
    projects = dashboard(report)
    assert (projects["name"], projects["light"]) == ("Proyectos", "red")
    delayed = indicator(report, "projects.delayed")
    assert delayed["name"] == "Proyectos retrasados"
    assert (delayed["value"], delayed["previous_value"], delayed["change"]) == (4, 6, -2)
    assert (delayed["target"], delayed["deviation"], delayed["on_track"]) == (3, -1, False)
    assert [point["month"] for point in delayed["series"]][-2:] == [9, 10]
    assert len(delayed["series"]) == 12
    # Not recorded for October and cannot be rebuilt: left empty, not filled with today's.
    assert indicator(report, "projects.active")["value"] is None
    tables = {table["key"]: table["rows"] for table in projects["tables"]}
    assert tables["projects.milestones_reached"] == [
        ["Plaza central", "Hito 1", "2026-10-05", "2026-10-09"],
        ["Plaza central", "Hito 3", "2026-09-01", "2026-10-30"],
    ]
    assert tables["projects.milestones_overdue"] == [["Plaza central", "Hito 2", "2026-10-20", 11]]


def test_a_closed_report_does_not_change_when_its_data_is_edited(client):
    municipality = admin(client)
    project = october(municipality)
    report = close(client, {"projects": "Comentario."}).json()
    document = client.get(f"{API}/{report['id']}/pdf").content
    # Everything the report came from changes afterwards.
    with admin_session() as session, session.begin():
        for row in session.scalars(select(IndicatorSnapshot)):
            row.value = 99
        for row in session.scalars(select(IndicatorTarget)):
            row.value = 1
        session.scalar(select(DashboardStatus)).color = "green"
        stored = session.get(type(project), project.id)
        stored.manual_progress = 90
        stored.name = "Otro nombre"
        for milestone in stored.milestones:
            milestone.completed_on = date(2026, 10, 1)

    again = client.get(f"{API}/{report['id']}").json()

    assert again["content"] == report["content"]
    assert client.get(f"{API}/{report['id']}/pdf").content == document


@pytest.mark.parametrize(("year", "month"), [(2026, 11), (2026, 12), (2027, 1)])
def test_a_month_that_has_not_ended_cannot_be_closed(client, year, month):
    admin(client)

    response = close(client, year=year, month=month)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "month_not_over"


def test_a_closed_month_cannot_be_closed_again(client):
    admin(client)
    close(client)

    response = close(client)

    assert response.status_code == 409
    assert client.get(f"{API}/preview/2026/10").status_code == 409


def test_comments_are_only_for_the_municipalitys_dashboards(client):
    admin(client)

    assert close(client, {"social": "No está habilitado."}).status_code == 422
    assert close(client, {"projects": "x" * 2001}).status_code == 422
    assert client.get(API).json() == []


def test_the_preview_shows_what_closing_would_freeze(client):
    municipality = admin(client)
    october(municipality)

    preview = client.get(f"{API}/preview/2026/10")

    assert preview.status_code == 200
    assert preview.json()["version"] is None
    assert preview.json()["comments"] == {}
    assert dashboard(preview.json())["light"] == "red"
    assert client.get(API).json() == []


def test_only_municipality_admins_handle_reports(client):
    municipality = make_municipality("Noetinger")
    user = make_user("ana@noetinger.test")
    make_membership(user, municipality, grants={"projects": "admin"})
    login(client, "ana@noetinger.test")

    assert client.get(API).status_code == 403
    assert close(client).status_code == 403


def test_reports_of_another_municipality_are_invisible(client):
    admin(client, "Saira", "luis@saira.test")
    report = close(client).json()
    client.post("/api/auth/logout")
    admin(client)

    assert client.get(API).json() == []
    assert client.get(f"{API}/{report['id']}").status_code == 404
    assert client.get(f"{API}/{report['id']}/pdf").status_code == 404
    assert client.post(f"{API}/{report['id']}/reopen").status_code == 404


# Reopening


def test_reopening_creates_a_new_version_and_an_audit_entry(client):
    municipality = admin(client)
    october(municipality)
    first = close(client, {"projects": "Primera versión."}).json()

    response = client.post(f"{API}/{first['id']}/reopen")

    assert response.status_code == 201
    draft = response.json()
    assert (draft["version"], draft["status"]) == (2, "draft")
    listed = {(r["version"], r["status"]) for r in client.get(API).json()}
    assert listed == {(1, "superseded"), (2, "draft")}
    assert client.get(f"{API}/preview/2026/10").json()["comments"] == {
        "projects": "Primera versión."
    }
    with admin_session() as session:
        entries = session.scalars(
            select(AuditLog)
            .where(AuditLog.entity_type == "monthly_reports")
            .order_by(AuditLog.created_at)
        ).all()
    reopened = [e for e in entries if e.changes and e.changes.get("reopened")]
    assert {(e.action, e.entity_id) for e in reopened} == {
        ("update", first["id"]),
        ("create", draft["id"]),
    }
    assert all(e.user_id is not None for e in reopened)
    # The superseded version keeps its content; closing again freezes a new one.
    assert client.get(f"{API}/{first['id']}").json()["content"] == first["content"]
    second = close(client, {"projects": "Segunda versión."}).json()
    assert (second["id"], second["version"], second["status"]) == (draft["id"], 2, "closed")


def test_only_a_closed_version_can_be_reopened(client):
    admin(client)
    first = close(client).json()
    draft = client.post(f"{API}/{first['id']}/reopen").json()

    assert client.post(f"{API}/{first['id']}/reopen").status_code == 409
    assert client.post(f"{API}/{draft['id']}/reopen").status_code == 409
    assert client.get(f"{API}/{draft['id']}/pdf").status_code == 409


# The PDF


FIXED = ReportDocument(
    content={
        "municipality": {"name": "Villa Prueba", "kind": "commune"},
        "year": 2026,
        "month": 10,
        "dashboards": [
            {
                "key": "projects",
                "name": "Proyectos",
                "light": "yellow",
                "indicators": [
                    {
                        "key": "projects.delayed",
                        "name": "Proyectos retrasados",
                        "unit": None,
                        "higher_is_better": False,
                        "aggregate": True,
                        "value": 3,
                        "previous_value": 6,
                        "change": -3,
                        "target": 4,
                        "deviation": 1,
                        "on_track": True,
                        "series": [
                            {"year": 2026, "month": m, "value": v, "target": 4}
                            for m, v in zip(
                                range(1, 11), [5, 6, None, 7, 6, 6, 5, 4, 6, 3], strict=True
                            )
                        ],
                    },
                    {
                        "key": "projects.budget_executed_ratio",
                        "name": "Presupuesto ejecutado",
                        "unit": "ratio",
                        "higher_is_better": True,
                        "aggregate": True,
                        "value": 0.4645,
                        "previous_value": 0.4729,
                        "change": -0.0084,
                        "target": 0.5,
                        "deviation": -0.0355,
                        "on_track": False,
                        "series": [],
                    },
                    {
                        "key": "projects.internal",
                        "name": "Dato interno",
                        "unit": None,
                        "higher_is_better": True,
                        "aggregate": False,
                        "value": 1234567.5,
                        "previous_value": None,
                        "change": None,
                        "target": None,
                        "deviation": None,
                        "on_track": None,
                        "series": [],
                    },
                ],
                "tables": [
                    {
                        "key": "projects.milestones_reached",
                        "title": "Hitos alcanzados en el mes",
                        "columns": [
                            {"title": "Proyecto", "kind": "text"},
                            {"title": "Alcanzado el", "kind": "date"},
                        ],
                        "rows": [["Plaza central", "2026-10-09"]],
                    }
                ],
            },
            {
                "key": "social",
                "name": "Social",
                "light": None,
                "indicators": [],
                "tables": [],
            },
        ],
    },
    comments={"projects": "Un mes con lluvias: “obras” demoradas − ninguna cancelada 🌧."},
    version=2,
    closed_at=datetime(2026, 11, 3, 14, 30, tzinfo=UTC),
)

# The text extraction of the fixed report, stored: the document must keep reading so.
FIXED_TEXT = """\
COMUNA
Villa Prueba
Informe de gestión de octubre de 2026
Versión 2, cerrada el 03/11/2026.
Resumen del mes
Tablero Estado del mes Metas
Proyectos 1 de 2 en metaCon atención
Social Sin metasSin estado
Proyectos Estado del mes: Con atención
Comentario de la gestión
Un mes con lluvias: “obras” demoradas - ninguna cancelada ?.
Indicador Valor Mes anterior Variación Meta Estado 12 meses
Proyectos retrasados 3 6 -3 4 En meta
Presupuesto ejecutado 46,5 % 47,3 % -0,8 p.p. 50 % Fuera de meta
Dato interno 1.234.567,5 — — — Sin meta
Hitos alcanzados en el mes
Proyecto Alcanzado el
Plaza central 09/10/2026
Social Estado del mes: Sin estado
Sin indicadores.
Villa Prueba · Informe de gestión de octubre de 2026 · versión 2 Página 1 de 1"""


def test_the_same_report_always_gives_the_same_document():
    first, second = render_report(FIXED), render_report(FIXED)

    assert first == second
    assert first.startswith(b"%PDF-")
    assert b"D:20261103143000Z" in first


def test_the_document_matches_its_stored_text_with_argentine_formats():
    # Characters the PDF's base fonts lack are replaced, never dropped silently.
    assert pdf_text(render_report(FIXED)) == FIXED_TEXT


def test_the_public_rendition_masks_small_counts_and_leaves_out_what_is_not_aggregate():
    public = ReportDocument(**{**FIXED.__dict__, "public_threshold": 5})

    text = pdf_text(render_report(public))

    # 3 is hidden, and so is what would give it away; 6 is above the threshold.
    assert "Proyectos retrasados menos de 5 6 — 4 —" in text
    assert "Proyectos 0 de 1 en meta" in text
    assert "Presupuesto ejecutado 46,5 %" in text
    assert "Dato interno" not in text
    assert "«menos de 5»" in text
    assert render_report(public) == render_report(public)


def test_the_pdf_download_is_named_after_the_municipality_and_month(client):
    admin(client)
    report = close(client).json()

    response = client.get(f"{API}/{report['id']}/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == (
        'attachment; filename="informe-noetinger-2026-10-v1.pdf"'
    )
    assert "Informe de gestión de octubre de 2026" in pdf_text(response.content)


def test_a_long_report_breaks_pages_without_splitting_a_row(client):
    many = {
        **FIXED.content,
        "dashboards": [
            {**FIXED.content["dashboards"][0], "key": f"d{n}", "name": f"Tablero {n}"}
            for n in range(8)
        ],
    }
    reader = pypdf.PdfReader(
        io.BytesIO(render_report(ReportDocument(many, {}, 1, FIXED.closed_at)))
    )

    assert len(reader.pages) > 1
    for number, page in enumerate(reader.pages, start=1):
        assert f"Página {number} de {len(reader.pages)}" in page.extract_text()
    # Every indicator row is whole on one page.
    rows = sum(page.extract_text().count("Proyectos retrasados 3 6 -3 4 En meta")
               for page in reader.pages)  # fmt: skip
    assert rows == 8


def test_reports_keep_the_closing_time_and_versions_in_the_database(client):
    admin(client)
    report = close(client).json()

    with admin_session() as session:
        stored = session.get(MonthlyReport, report["id"])
    assert stored.closed_at.microsecond == 0
    assert stored.content is not None
