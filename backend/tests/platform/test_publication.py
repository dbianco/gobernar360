"""The public page: what is published, and the routes that serve it without a session."""

import io
from datetime import date

import pypdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import InternalError, ProgrammingError

from gobernar360.core.db import public_session
from gobernar360.platform.clock import get_today
from gobernar360.platform.models import (
    AuditLog,
    DashboardStatus,
    IndicatorSnapshot,
    Person,
    PublicIndicator,
    PublicSite,
)
from gobernar360.platform.snapshots import take_snapshots
from tests.factories import (
    admin_session,
    enable_dashboards,
    login,
    make_membership,
    make_municipality,
    make_user,
)

TODAY = date(2026, 11, 20)
PUBLICATION = "/api/publication"
PUBLIC = "/api/public"


@pytest.fixture(autouse=True)
def pinned_today(client):
    client.app.dependency_overrides[get_today] = lambda: TODAY


@pytest.fixture
def anonymous(client):
    """A second client of the same application, with no session cookie at all."""
    with TestClient(client.app) as other:
        yield other


def add(*rows):
    with admin_session() as session, session.begin():
        session.add_all(rows)


def admin(client, name="Noetinger", email="ana@noetinger.test", enable=("demo",)):
    municipality = make_municipality(name)
    make_membership(make_user(email), municipality, admin=True, enable=list(enable))
    login(client, email)
    return municipality


def turn_on(client, slug="noetinger", threshold=5):
    return client.put(
        f"{PUBLICATION}/settings",
        json={"enabled": True, "slug": slug, "small_count_threshold": threshold},
    )


def publish(client, kind, key, published=True):
    return client.put(f"{PUBLICATION}/{kind}/{key}", json={"published": published})


def demo_page(client, threshold=5):
    """Noetinger's page on, the demo dashboard and its aggregate indicator published."""
    municipality = admin(client)
    turn_on(client, threshold=threshold)
    publish(client, "dashboards", "demo")
    publish(client, "indicators", "demo.day")
    return municipality


def site(anonymous, slug="noetinger"):
    return anonymous.get(f"{PUBLIC}/{slug}")


# Turning the page on


def test_a_municipality_that_did_not_turn_the_page_on_has_none(client, anonymous, demo_dashboard):
    admin(client)
    publish(client, "dashboards", "demo")

    assert client.get(PUBLICATION).json()["enabled"] is False
    assert site(anonymous).status_code == 404
    assert anonymous.get(f"{PUBLIC}/noetinger/indicators/demo.day").status_code == 404
    assert anonymous.get(f"{PUBLIC}/noetinger/reports/2026/10").status_code == 404


def test_the_page_shows_what_is_published_without_a_session(client, anonymous, demo_dashboard):
    municipality = demo_page(client)
    add(
        DashboardStatus(municipality_id=municipality.id, dashboard_key="demo", year=2026,
                        month=10, color="yellow"),
        DashboardStatus(municipality_id=municipality.id, dashboard_key="demo", year=2025,
                        month=10, color="red"),  # More than a year ago.
    )  # fmt: skip
    publish(client, "dashboards", "demo")  # Lights are copied on every change.

    response = site(anonymous)

    assert response.status_code == 200
    body = response.json()
    assert (body["slug"], body["name"], body["kind"]) == ("noetinger", "Noetinger", "municipality")
    assert body["dashboards"] == [
        {"key": "demo", "name": "demo", "lights": [{"year": 2026, "month": 10, "color": "yellow"}]}
    ]
    assert [indicator["key"] for indicator in body["indicators"]] == ["demo.day"]
    assert body["indicators"][0]["value"] == TODAY.day
    assert body["reports"] == []
    assert "g360_session" not in anonymous.cookies


def test_the_page_address_is_chosen_and_unique(client, demo_dashboard):
    admin(client, "Saira", "luis@saira.test")
    turn_on(client, slug="saira")
    client.post("/api/auth/logout")
    admin(client)

    taken = turn_on(client, slug="saira")
    invalid = turn_on(client, slug="No Vale!")

    assert taken.status_code == 409
    assert taken.json()["error"]["code"] == "slug_taken"
    assert invalid.status_code == 422
    assert turn_on(client, slug="  Noetinger-Transparente ").json()["slug"] == (
        "noetinger-transparente"
    )


def test_changing_the_address_moves_the_page(client, anonymous, demo_dashboard):
    demo_page(client)

    turn_on(client, slug="transparencia-noetinger")

    assert site(anonymous).status_code == 404
    assert site(anonymous, "transparencia-noetinger").status_code == 200


def test_only_municipality_admins_change_the_publication(client, demo_dashboard):
    municipality = make_municipality("Noetinger")
    make_membership(make_user("ana@noetinger.test"), municipality, grants={"demo": "admin"})
    login(client, "ana@noetinger.test")

    assert client.get(PUBLICATION).status_code == 403
    assert turn_on(client).status_code == 403
    assert publish(client, "indicators", "demo.day").status_code == 403


def test_publication_changes_are_audited(client, demo_dashboard):
    demo_page(client)

    with admin_session() as session:
        types = set(session.scalars(select(AuditLog.entity_type)))
    assert {"public_settings", "published_dashboards", "published_indicators"} <= types


# What can be published


def test_an_indicator_not_declared_aggregate_cannot_be_published(client, anonymous, demo_dashboard):
    demo_page(client)

    response = publish(client, "indicators", "demo.state")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "not_aggregate"
    assert anonymous.get(f"{PUBLIC}/noetinger/indicators/demo.state").status_code == 404
    choices = client.get(PUBLICATION).json()["dashboards"][0]["indicators"]
    assert {(c["key"], c["aggregate"], c["published"]) for c in choices} == {
        ("demo.day", True, True),
        ("demo.state", False, False),
    }


def test_an_indicator_needs_its_dashboard_published_first(client, demo_dashboard):
    admin(client)
    turn_on(client)

    response = publish(client, "indicators", "demo.day")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "dashboard_not_published"


def test_unknown_or_disabled_dashboards_and_indicators_cannot_be_published(client):
    admin(client, enable=("projects",))
    turn_on(client)

    assert publish(client, "dashboards", "social").status_code == 404
    assert publish(client, "dashboards", "nothing").status_code == 404
    assert publish(client, "indicators", "social.people").status_code == 404
    assert publish(client, "indicators", "nothing").status_code == 404


def test_public_routes_never_expose_an_unpublished_indicator(client, anonymous, demo_dashboard):
    municipality = admin(client)
    turn_on(client)
    publish(client, "dashboards", "demo")
    add(IndicatorSnapshot(municipality_id=municipality.id, dashboard_key="demo",
                          indicator_key="demo.day", year=2026, month=10, value=31))  # fmt: skip

    body = site(anonymous).json()

    assert body["indicators"] == []
    assert anonymous.get(f"{PUBLIC}/noetinger/indicators/demo.day").status_code == 404
    assert anonymous.get(f"{PUBLIC}/noetinger/indicators/demo.state").status_code == 404


# Small counts


def test_small_counts_are_masked_with_whatever_would_reveal_them(client, anonymous, demo_dashboard):
    municipality = demo_page(client, threshold=25)
    add(
        IndicatorSnapshot(municipality_id=municipality.id, dashboard_key="demo",
                          indicator_key="demo.day", year=2026, month=10, value=31),
        IndicatorSnapshot(municipality_id=municipality.id, dashboard_key="demo",
                          indicator_key="demo.day", year=2025, month=11, value=0),
    )  # fmt: skip
    publish(client, "indicators", "demo.day")

    day = anonymous.get(f"{PUBLIC}/noetinger/indicators/demo.day").json()

    # Today is the 20th: below 25.
    assert (day["value"], day["value_below"]) == (None, 25)
    assert (day["previous_value"], day["previous_below"]) == (31, None)
    assert day["change_previous_month"] is None
    assert day["on_track"] is None
    assert (day["last_year_value"], day["last_year_below"]) == (0, None)
    assert day["series"][-1] == {
        "year": 2026, "month": 11, "value": None, "below": 25, "target": None
    }  # fmt: skip


def test_a_threshold_of_zero_or_one_masks_nothing(client, anonymous, demo_dashboard):
    demo_page(client, threshold=1)

    day = anonymous.get(f"{PUBLIC}/noetinger/indicators/demo.day").json()

    assert (day["value"], day["value_below"]) == (TODAY.day, None)


# Unpublishing


def test_unpublishing_removes_access_at_once(client, anonymous, demo_dashboard):
    demo_page(client)
    assert anonymous.get(f"{PUBLIC}/noetinger/indicators/demo.day").status_code == 200

    publish(client, "indicators", "demo.day", published=False)
    assert anonymous.get(f"{PUBLIC}/noetinger/indicators/demo.day").status_code == 404
    assert site(anonymous).json()["indicators"] == []

    publish(client, "indicators", "demo.day")
    publish(client, "dashboards", "demo", published=False)
    assert site(anonymous).json()["dashboards"] == []
    assert anonymous.get(f"{PUBLIC}/noetinger/indicators/demo.day").status_code == 404
    # The indicator went with its dashboard.
    assert client.get(PUBLICATION).json()["dashboards"][0]["indicators"][0]["published"] is False

    client.put(
        f"{PUBLICATION}/settings",
        json={"enabled": False, "slug": "noetinger", "small_count_threshold": 5},
    )
    assert site(anonymous).status_code == 404
    with admin_session() as session:
        assert session.scalar(select(PublicSite)) is None
        assert session.scalar(select(PublicIndicator)) is None


def test_a_dashboard_the_operator_disables_leaves_the_page_at_once(
    client, anonymous, demo_dashboard
):
    municipality = demo_page(client)
    client.post("/api/auth/logout")
    make_user("operator@gobernar360.test", operator=True)
    login(client, "operator@gobernar360.test")

    client.put(f"/api/platform/municipalities/{municipality.id}/dashboards", json={"keys": []})

    assert site(anonymous).json()["dashboards"] == []
    assert anonymous.get(f"{PUBLIC}/noetinger/indicators/demo.day").status_code == 404


def test_snapshots_refresh_the_published_evolution(client, anonymous, demo_dashboard):
    demo_page(client)
    before = anonymous.get(f"{PUBLIC}/noetinger/indicators/demo.day").json()

    take_snapshots(date(2026, 11, 27))

    after = anonymous.get(f"{PUBLIC}/noetinger/indicators/demo.day").json()
    assert (before["value"], after["value"]) == (20, 27)


# Isolation


def test_public_routes_run_with_no_tenant_and_no_session(client, anonymous, demo_dashboard):
    demo_page(client)

    assert site(anonymous).status_code == 200
    with public_session() as db:
        assert db.scalar(text("SELECT current_user")) == "gobernar360_public"
        assert db.scalar(text("SELECT current_setting('app.municipality_id', true)")) in (None, "")
        assert db.scalar(select(PublicSite.slug)) == "noetinger"
    for table in ("users", "sessions", "memberships", "people", "indicator_snapshots",
                  "monthly_reports", "public_settings", "social_interventions"):  # fmt: skip
        with pytest.raises(ProgrammingError, match="permission denied"), public_session() as db:
            db.execute(text(f'SELECT 1 FROM "{table}" LIMIT 1'))
    # Writing is refused twice over: a read-only transaction, of a role that may only read.
    with pytest.raises((InternalError, ProgrammingError)), public_session() as db:
        db.execute(text("DELETE FROM public_sites"))


def test_one_municipalitys_address_never_returns_anothers_rows(client, anonymous, demo_dashboard):
    demo_page(client)
    client.post("/api/auth/logout")
    saira = admin(client, "Saira", "luis@saira.test")
    turn_on(client, slug="saira")
    publish(client, "dashboards", "demo")
    add(DashboardStatus(municipality_id=saira.id, dashboard_key="demo", year=2026, month=11,
                        color="red"))  # fmt: skip
    publish(client, "dashboards", "demo")

    noetinger, other = site(anonymous).json(), site(anonymous, "saira").json()

    assert noetinger["name"] == "Noetinger" and other["name"] == "Saira"
    assert [i["key"] for i in noetinger["indicators"]] == ["demo.day"]
    assert other["indicators"] == []
    assert noetinger["dashboards"][0]["lights"] == []
    assert other["dashboards"][0]["lights"] == [{"year": 2026, "month": 11, "color": "red"}]
    assert anonymous.get(f"{PUBLIC}/saira/indicators/demo.day").status_code == 404


def test_a_municipality_cannot_write_anothers_public_rows(client, demo_dashboard):
    from gobernar360.core.db import tenant_session

    noetinger = demo_page(client)
    saira = make_municipality("Saira")

    with pytest.raises(ProgrammingError), tenant_session(saira.id) as db:
        db.execute(text("DELETE FROM public_sites"))
        # Row-level security hides the rows from writers of another municipality.
        assert db.execute(text("SELECT count(*) FROM public_sites")).scalar() == 1
        db.add(PublicSite(municipality_id=noetinger.id, slug="x", name="x", kind="commune",
                          small_count_threshold=0))  # fmt: skip
        db.flush()
    with admin_session() as session:
        assert session.scalar(select(PublicSite.slug)) == "noetinger"


# Reports on the public page


def close_and_publish(client, comments=None):
    report = client.post(
        "/api/reports/2026/10/close", json={"comments": comments or {"demo": "Un buen mes."}}
    ).json()
    return report, client.put(f"/api/reports/{report['id']}/publication", json={"published": True})


def test_a_published_report_is_listed_and_downloadable_masked(client, anonymous, demo_dashboard):
    municipality = demo_page(client)
    add(IndicatorSnapshot(municipality_id=municipality.id, dashboard_key="demo",
                          indicator_key="demo.day", year=2026, month=10, value=3))  # fmt: skip

    report, response = close_and_publish(client)

    assert response.status_code == 204
    assert site(anonymous).json()["reports"] == [
        {"year": 2026, "month": 10, "version": 1, "closed_at": report["closed_at"]}
    ]
    document = anonymous.get(f"{PUBLIC}/noetinger/reports/2026/10")
    assert document.headers["content-type"] == "application/pdf"
    text_of = "\n".join(
        p.extract_text() for p in pypdf.PdfReader(io.BytesIO(document.content)).pages
    )
    assert "Versión pública" in text_of
    assert "menos de 5" in text_of
    assert "Un buen mes." in text_of


def test_unpublishing_or_reopening_a_report_removes_it_at_once(client, anonymous, demo_dashboard):
    demo_page(client)
    report, _ = close_and_publish(client)

    client.put(f"/api/reports/{report['id']}/publication", json={"published": False})
    assert anonymous.get(f"{PUBLIC}/noetinger/reports/2026/10").status_code == 404

    client.put(f"/api/reports/{report['id']}/publication", json={"published": True})
    assert anonymous.get(f"{PUBLIC}/noetinger/reports/2026/10").status_code == 200
    client.post(f"/api/reports/{report['id']}/reopen")
    assert anonymous.get(f"{PUBLIC}/noetinger/reports/2026/10").status_code == 404
    assert site(anonymous).json()["reports"] == []


def test_a_draft_cannot_be_published(client, demo_dashboard):
    demo_page(client)
    report, _ = close_and_publish(client)
    draft = client.post(f"/api/reports/{report['id']}/reopen").json()

    response = client.put(f"/api/reports/{draft['id']}/publication", json={"published": True})

    assert response.status_code == 409


@pytest.mark.parametrize(
    "comment",
    ["Se asistió a Juana Pérez.", "Caso de PEREZ JUANA", "DNI 30.222.111", "dni 30222111"],
)
def test_a_report_whose_comments_name_a_person_cannot_be_published(
    client, anonymous, demo_dashboard, comment
):
    municipality = demo_page(client)
    add(Person(municipality_id=municipality.id, first_name="Juana", last_name="Pérez",
               dni="30222111"))  # fmt: skip

    _, response = close_and_publish(client, {"demo": comment})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "personal_data"
    assert site(anonymous).json()["reports"] == []


def test_people_of_another_municipality_do_not_block_publishing(client, demo_dashboard):
    demo_page(client)
    saira = make_municipality("Saira")
    add(Person(municipality_id=saira.id, first_name="Juana", last_name="Pérez", dni="1234567"))

    _, response = close_and_publish(client, {"demo": "Reunión con Juana Pérez."})

    assert response.status_code == 204


# Serving


def test_public_answers_can_be_cached_but_are_always_checked_again(
    client, anonymous, demo_dashboard
):
    demo_page(client)
    first = site(anonymous)

    again = anonymous.get(f"{PUBLIC}/noetinger", headers={"If-None-Match": first.headers["etag"]})
    publish(client, "indicators", "demo.day", published=False)
    changed = anonymous.get(f"{PUBLIC}/noetinger", headers={"If-None-Match": first.headers["etag"]})

    assert first.headers["cache-control"] == "public, no-cache"
    assert again.status_code == 304
    assert changed.status_code == 200
    assert changed.json()["indicators"] == []


def test_public_routes_are_rate_limited(client, anonymous, demo_dashboard, monkeypatch):
    from gobernar360.core.config import get_settings

    demo_page(client)
    monkeypatch.setattr(get_settings(), "public_rate_limit_per_minute", 3)

    answers = [site(anonymous).status_code for _ in range(4)]

    assert answers == [200, 200, 200, 429]
    limited = site(anonymous)
    assert limited.json()["error"]["code"] == "rate_limited"
    assert int(limited.headers["retry-after"]) > 0


def test_public_routes_need_no_csrf_header_and_accept_no_writes(anonymous):
    assert anonymous.post(f"{PUBLIC}/noetinger").status_code in (403, 405)
    assert anonymous.get(f"{PUBLIC}/nowhere").status_code == 404


def test_indicators_of_disabled_modules_in_the_demo_are_not_offered(client, demo_dashboard):
    municipality = admin(client)
    enable_dashboards(municipality, ["projects"])

    keys = [d["key"] for d in client.get(PUBLICATION).json()["dashboards"]]

    assert keys == ["projects", "demo"]
