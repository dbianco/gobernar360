"""CSV downloads of the cases and of the per-area report."""

import csv
import io

from tests.complaints.factories import (
    BASE,
    Setup,
    at,
    complaints_member,
    make_area,
    make_person,
    pin_clock,
    signed_in,
)


def _rows(response):
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))


def test_the_cases_csv_has_one_row_per_complaint_with_its_clock(client):
    setup = Setup(signed_in(client, "viewer"), target_days=5)
    person = make_person(setup.municipality)
    setup.complaint(
        "closed", received_at=at(2, hour=9), person=person, address="=HYPERLINK(1)"
    )  # resolved Tuesday 3
    setup.complaint("assigned", received_at=at(9, hour=9))
    setup.complaint("rejected", received_at=at(2, hour=8))
    pin_clock(client, at(12))

    header, *rows = _rows(client.get(f"{BASE}/export/complaints.csv"))

    assert header == [
        "number",
        "received_on",
        "type",
        "area",
        "zone",
        "address",
        "state",
        "complainant",
        "target_business_days",
        "business_days_used",
        "business_days_left",
        "deadline",
        "clock_status",
        "resolved_on",
        "resolution_business_days",
        "resolved_on_time",
    ]
    by_number = {row[0]: dict(zip(header, row, strict=True)) for row in rows}
    closed, open_one, rejected = by_number["1"], by_number["2"], by_number["3"]
    assert closed["address"] == "'=HYPERLINK(1)"
    assert closed["complainant"] == "Fernández, Lucía"
    assert (closed["state"], closed["resolved_on"], closed["resolution_business_days"]) == (
        "closed",
        "2026-03-03",
        "1",
    )
    assert (closed["resolved_on_time"], closed["clock_status"], closed["business_days_left"]) == (
        "yes",
        "on_time",
        "",
    )
    assert (open_one["business_days_used"], open_one["business_days_left"]) == ("3", "2")
    assert (open_one["deadline"], open_one["clock_status"]) == ("2026-03-16", "at_risk")
    assert (open_one["resolution_business_days"], open_one["complainant"]) == ("", "")
    assert (rejected["state"], rejected["clock_status"], rejected["resolved_on_time"]) == (
        "rejected",
        "",
        "",
    )
    # Oldest first.
    assert [row[0] for row in rows] == ["3", "1", "2"]


def test_the_cases_csv_takes_the_summarys_period(client):
    setup = Setup(signed_in(client, "viewer"))
    setup.complaint(received_at=at(2, month=2))
    setup.complaint(received_at=at(2, month=3))
    pin_clock(client, at(12))

    _, *february = _rows(
        client.get(
            f"{BASE}/export/complaints.csv", params={"from": "2026-02-01", "to": "2026-02-28"}
        )
    )

    assert [row[1] for row in february] == ["2026-02-02"]


def test_the_area_report_has_every_area(client):
    setup = Setup(signed_in(client, "viewer"), target_days=5)
    make_area(setup.municipality, "Zoonosis")
    setup.complaint("closed", received_at=at(2))
    setup.complaint("assigned", received_at=at(2))
    pin_clock(client, at(12))

    header, *rows = _rows(client.get(f"{BASE}/export/areas.csv"))

    assert header == [
        "area",
        "received",
        "resolved",
        "resolved_on_time",
        "on_time_percent",
        "median_resolution_business_days",
        "p90_resolution_business_days",
        "open_today",
        "at_risk_today",
        "overdue_today",
    ]
    assert rows == [
        ["Alumbrado Público", "2", "1", "1", "100.0", "1", "1", "1", "0", "1"],
        ["Zoonosis", "0", "0", "0", "", "", "", "0", "0", "0"],
    ]


def test_downloads_need_the_dashboard_and_stay_inside_the_municipality(client):
    other = Setup(complaints_member("admin", email="x@saira.test", municipality_name="Saira"))
    other.complaint()
    signed_in(client, "viewer")

    assert _rows(client.get(f"{BASE}/export/complaints.csv"))[1:] == []
    assert _rows(client.get(f"{BASE}/export/areas.csv"))[1:] == []
    client.post("/api/auth/logout")
    signed_out = client.get(f"{BASE}/export/complaints.csv")
    assert signed_out.status_code == 401
