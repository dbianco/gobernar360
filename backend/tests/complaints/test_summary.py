"""The analysis on known data sets, and what the dashboard adds to the general overview."""

import csv
import io
import statistics
from datetime import date

import pytest

from gobernar360.dashboards.complaints.stats import median, percentile
from tests.complaints.factories import (
    BASE,
    at,
    make_area,
    make_complaint,
    make_type,
    make_zone,
    pin_clock,
    signed_in,
)
from tests.factories import current_overview

# Business days after Monday 2 March 2026 -> the day they are reached.
REACHED = {1: 3, 2: 4, 3: 5, 4: 6, 5: 9, 7: 11, 8: 12, 10: 16}


def test_percentiles_interpolate_like_a_spreadsheet():
    assert median([]) is None
    assert median([7]) == 7
    assert median([3, 1, 2]) == 2
    assert median([1, 2, 3, 4]) == 2.5
    assert percentile([1, 2, 4, 7, 10], 0.9) == pytest.approx(8.8)
    assert percentile([2, 3, 5, 8], 0.9) == pytest.approx(7.1)
    assert percentile([5, 1], 0) == 1
    assert percentile([5, 1], 1) == 5


class KnownSet:
    """Two types in two areas, with resolution times chosen by hand.

    Lamps (target 5): 1, 2, 4, 7, 10 days -> median 4, p90 8.8, on time 3 of 5.
    Waste (target 3): 2, 3, 5, 8 days -> median 4, p90 7.1, on time 2 of 4. One of them
    was moved to the lights area, so per area: lights 1, 2, 4, 7, 8, 10; waste 2, 3, 5.
    Plus one open and one rejected complaint, which have no resolution time.
    """

    def __init__(self, municipality):
        self.municipality = municipality
        self.lights, self.cleaning = (
            make_area(municipality, "Alumbrado"),
            make_area(municipality, "Higiene"),
        )
        self.zone, self.north = make_zone(municipality, "Centro"), make_zone(municipality, "Norte")
        self.lamp = make_type(municipality, self.lights, "Luminaria apagada", target_days=5)
        self.waste = make_type(municipality, self.cleaning, "Residuos", target_days=3)
        for days in (1, 2, 4, 7, 10):
            self._solved(self.lamp, days)
        for days in (2, 3, 5):
            self._solved(self.waste, days)
        self._solved(self.waste, 8, area=self.lights, closed=True)
        make_complaint(municipality, self.lamp, self.north, at(2), [(at(3), "assigned")])
        make_complaint(municipality, self.waste, self.north, at(2), [(at(3), "rejected")])

    def _solved(self, complaint_type, days, area=None, closed=False):
        steps = [(at(2, hour=11), "assigned"), (at(REACHED[days]), "resolved")]
        if closed:
            steps.append((at(REACHED[days] + 1), "closed"))
        make_complaint(
            self.municipality, complaint_type, self.zone, at(2, hour=9), steps, area=area
        )


def _row(rows, name):
    return next(row for row in rows if row["name"] == name)


def test_resolution_times_by_type_and_area_on_a_known_set(client):
    KnownSet(signed_in(client, "viewer"))
    pin_clock(client, at(20))

    summary = client.get(f"{BASE}/summary").json()

    lamp, waste = (
        _row(summary["by_type"], "Luminaria apagada"),
        _row(summary["by_type"], "Residuos"),
    )
    assert {k: lamp[k] for k in ("received", "resolved", "on_time", "median_days", "p90_days")} == {
        "received": 6,
        "resolved": 5,
        "on_time": 3,
        "median_days": 4,
        "p90_days": 8.8,
    }
    assert lamp["on_time_ratio"] == 0.6
    assert (waste["received"], waste["resolved"], waste["on_time"]) == (5, 4, 2)
    assert (waste["median_days"], waste["p90_days"], waste["on_time_ratio"]) == (4, 7.1, 0.5)
    lights, cleaning = _row(summary["by_area"], "Alumbrado"), _row(summary["by_area"], "Higiene")
    assert (lights["resolved"], lights["median_days"], lights["p90_days"]) == (6, 5.5, 9)
    assert (cleaning["resolved"], cleaning["median_days"], cleaning["p90_days"]) == (3, 3, 4.6)
    totals = summary["totals"]
    assert (totals["received"], totals["resolved"], totals["on_time"]) == (11, 9, 5)
    assert (totals["median_days"], totals["p90_days"]) == (4, 8.4)
    assert round(totals["on_time_ratio"], 4) == round(5 / 9, 4)
    assert summary["top_types"] == [
        {"name": "Luminaria apagada", "count": 6},
        {"name": "Residuos", "count": 5},
    ]
    assert summary["top_zones"] == [{"name": "Centro", "count": 9}, {"name": "Norte", "count": 2}]


def test_the_median_by_type_matches_the_cases_csv(client):
    KnownSet(signed_in(client, "viewer"))
    pin_clock(client, at(20))

    summary = client.get(f"{BASE}/summary").json()
    exported = client.get(f"{BASE}/export/complaints.csv")

    rows = list(csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig"))))
    for group in summary["by_type"]:
        days = [
            int(row["resolution_business_days"])
            for row in rows
            if row["type"] == group["name"] and row["resolution_business_days"]
        ]
        assert statistics.median(days) == group["median_days"], group["name"]
        on_time = sum(
            row["resolved_on_time"] == "yes" for row in rows if row["type"] == group["name"]
        )
        assert on_time == group["on_time"]


def test_the_period_is_chosen_by_date_received(client):
    data = KnownSet(signed_in(client, "viewer"))
    make_complaint(
        data.municipality, data.lamp, data.zone, at(2, month=2), [(at(3, month=2), "resolved")]
    )
    pin_clock(client, at(20))

    march = client.get(f"{BASE}/summary", params={"from": "2026-03-01", "to": "2026-03-31"})
    february = client.get(f"{BASE}/summary", params={"from": "2026-02-01", "to": "2026-02-28"})
    default = client.get(f"{BASE}/summary").json()

    assert march.json()["totals"]["received"] == 11
    assert march.json()["period"] == {"from": "2026-03-01", "to": "2026-03-31"}
    assert february.json()["totals"]["received"] == 1
    assert default["period"] == {"from": "2025-04-01", "to": "2026-03-20"}
    assert default["totals"]["received"] == 12
    backwards = client.get(f"{BASE}/summary", params={"from": "2026-03-02", "to": "2026-03-01"})
    assert backwards.status_code == 422


def test_received_against_resolved_per_month(client):
    municipality = signed_in(client, "viewer")
    area, zone = make_area(municipality), make_zone(municipality)
    kind = make_type(municipality, area, target_days=10)
    # Received in December, resolved in January: counts as resolved in January only.
    make_complaint(municipality, kind, zone, at(22, 12, year=2025), [(at(5, 1), "resolved")])
    make_complaint(municipality, kind, zone, at(15, 1), [(at(3, 2), "resolved")])
    make_complaint(municipality, kind, zone, at(10, 2), [(at(2, 3), "resolved")])
    make_complaint(municipality, kind, zone, at(5, 3), [(at(6, 3), "assigned")])
    # Resolved, reopened and resolved again: once, in the month of its last resolution.
    make_complaint(
        municipality,
        kind,
        zone,
        at(12, 1),
        [(at(13, 1), "resolved"), (at(2, 2), "reopened"), (at(4, 3), "resolved")],
    )
    pin_clock(client, at(20))

    monthly = client.get(
        f"{BASE}/summary", params={"from": "2026-01-01", "to": "2026-03-20"}
    ).json()["monthly"]

    assert monthly == [
        {"month": "2026-01", "received": 2, "resolved": 1},
        {"month": "2026-02", "received": 1, "resolved": 1},
        {"month": "2026-03", "received": 1, "resolved": 2},
    ]


def test_repeated_complaints_share_type_and_address_within_the_period(client):
    municipality = signed_in(client, "viewer")
    area, zone = make_area(municipality), make_zone(municipality)
    lamp = make_type(municipality, area, "Luminaria apagada")
    pothole = make_type(municipality, area, "Bache")
    for day, month, address in [
        (2, 3, "San Martín 100"),
        (20, 3, "  san martin   100 "),
        (25, 4, "SAN MARTÍN 100."),
    ]:
        make_complaint(municipality, lamp, zone, at(day, month), address=address)
    make_complaint(municipality, pothole, zone, at(3, 3), address="San Martín 100")
    make_complaint(municipality, lamp, zone, at(4, 3), address="San Martín 1000")
    pin_clock(client, at(30, 4))

    within_30 = client.get(f"{BASE}/summary").json()
    within_40 = client.get(f"{BASE}/summary", params={"repeat_days": 40}).json()

    assert within_30["repeat_days"] == 30
    assert [(g["type"], g["count"], g["numbers"]) for g in within_30["repeated"]] == [
        ("Luminaria apagada", 2, [1, 2])
    ]
    group = within_30["repeated"][0]
    assert (group["first_received"], group["last_received"], group["zone"]) == (
        "2026-03-02",
        "2026-03-20",
        "Centro",
    )
    assert [(g["count"], g["numbers"]) for g in within_40["repeated"]] == [(3, [1, 2, 3])]
    assert client.get(f"{BASE}/summary", params={"repeat_days": 0}).status_code == 422


def test_the_backlog_today_by_state_status_and_age(client):
    municipality = signed_in(client, "viewer")
    area, zone = make_area(municipality), make_zone(municipality)
    kind = make_type(municipality, area, target_days=5)
    today = date(2026, 3, 20)
    for received, steps in [
        (at(19), []),
        (at(12), [(at(12), "assigned")]),
        (at(2), [(at(2), "assigned"), (at(3), "in_progress")]),
        (at(2, 1), [(at(5, 1), "assigned"), (at(6, 1), "waiting")]),
        (at(2, 12, year=2025), [(at(3, 12, year=2025), "assigned")]),
        (at(2), [(at(3), "resolved")]),
    ]:
        make_complaint(municipality, kind, zone, received, steps)
    pin_clock(client, at(today.day))

    backlog = client.get(f"{BASE}/summary").json()["backlog"]

    assert (backlog["open"], backlog["paused"]) == (5, 1)
    assert {row["state"]: row["count"] for row in backlog["by_state"]} == {
        "received": 1,
        "assigned": 2,
        "in_progress": 1,
        "waiting": 1,
        "reopened": 0,
    }
    # Received Thursday 12: 6 business days by Friday 20, past a 5-day target. The one
    # waiting since January used 2 days before pausing.
    assert {row["status"]: row["count"] for row in backlog["by_status"]} == {
        "on_time": 2,
        "at_risk": 0,
        "overdue": 3,
    }
    assert backlog["overdue"] == 3
    assert [(row["min_days"], row["max_days"], row["count"]) for row in backlog["ageing"]] == [
        (0, 7, 1),
        (8, 15, 1),
        (16, 30, 1),
        (31, 60, 0),
        (61, 90, 1),
        (91, None, 1),
    ]


def test_an_empty_dashboard_has_an_empty_summary(client):
    signed_in(client, "viewer")

    summary = client.get(f"{BASE}/summary").json()

    assert summary["totals"] == {
        "received": 0,
        "resolved": 0,
        "on_time": 0,
        "on_time_ratio": None,
        "median_days": None,
        "p90_days": None,
    }
    assert summary["backlog"]["open"] == 0
    assert len(summary["monthly"]) == 12
    assert summary["by_type"] == summary["repeated"] == summary["top_zones"] == []


def test_the_overview_shows_the_headline_indicators(client):
    KnownSet(signed_in(client, "viewer"))
    pin_clock(client, at(20))

    overview = current_overview(client.get("/api/overview").json())

    section = next(s for s in overview if s["dashboard_key"] == "complaints")
    assert section["indicators"] == [
        {"key": "complaints.open", "value": 1, "unit": None},
        {"key": "complaints.overdue", "value": 1, "unit": None},
        {"key": "complaints.on_time_ratio", "value": 0.5556, "unit": "ratio"},
        {"key": "complaints.median_resolution_days", "value": 4, "unit": None},
    ]
    assert section["status"] == []


def test_the_overview_has_no_indicators_before_any_complaint(client):
    signed_in(client, "viewer")

    overview = client.get("/api/overview").json()

    assert [s["indicators"] for s in overview if s["dashboard_key"] == "complaints"] == [[]]


def test_groups_are_sorted_by_name_regardless_of_accents(client):
    municipality = signed_in(client, "viewer")
    area, zone = make_area(municipality), make_zone(municipality)
    for name in ("Ruidos molestos", "Árbol caído", "Poste dañado", "Pérdida de agua"):
        make_complaint(municipality, make_type(municipality, area, name), zone, at(2))
    pin_clock(client, at(20))

    summary = client.get(f"{BASE}/summary").json()

    expected = ["Árbol caído", "Pérdida de agua", "Poste dañado", "Ruidos molestos"]
    assert [row["name"] for row in summary["by_type"]] == expected
    assert [row["name"] for row in summary["top_types"]] == expected


@pytest.mark.parametrize("path", ["summary", "export/complaints.csv", "export/areas.csv"])
def test_a_period_longer_than_ten_years_is_refused(client, path):
    signed_in(client, "viewer")

    too_long = client.get(f"{BASE}/{path}", params={"from": "2016-02-28", "to": "2026-03-01"})
    longest = client.get(f"{BASE}/{path}", params={"from": "2016-03-21", "to": "2026-03-20"})

    assert too_long.status_code == 422
    assert too_long.json()["error"] == {
        "code": "validation_error",
        "message": "The period can cover at most 10 years.",
    }
    assert longest.status_code == 200
