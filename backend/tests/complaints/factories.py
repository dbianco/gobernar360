"""Builders for complaints-dashboard test data, written through the owner connection."""

from datetime import date, datetime

from gobernar360.dashboards.complaints.models import (
    Area,
    Complaint,
    ComplaintEvent,
    ComplaintType,
    Holiday,
    WorkingWeek,
    Zone,
)
from gobernar360.platform.clock import LOCAL_TIMEZONE, get_now, get_today
from gobernar360.platform.models import Municipality, Person
from tests.factories import admin_session, login, make_membership, make_municipality, make_user

BASE = "/api/dashboards/complaints"
EMAIL = "ana@noetinger.test"


def at(day: int, month: int = 3, hour: int = 10, year: int = 2026) -> datetime:
    """A moment in Argentine local time; March 2026 starts on a Sunday."""
    return datetime(year, month, day, hour, tzinfo=LOCAL_TIMEZONE)


def pin_clock(client, moment: datetime) -> None:
    """Make the API believe it is `moment`, for both reading and recording."""
    client.app.dependency_overrides[get_now] = lambda: moment
    client.app.dependency_overrides[get_today] = lambda: moment.date()


def complaints_member(
    level: str | None = "editor",
    email: str = EMAIL,
    municipality: Municipality | None = None,
    municipality_name: str = "Noetinger",
) -> Municipality:
    """Create a user with that level on the complaints dashboard; return their municipality."""
    municipality = municipality or make_municipality(municipality_name)
    grants = {"complaints": level} if level else {}
    make_membership(make_user(email), municipality, grants=grants, enable=["complaints"])
    return municipality


def signed_in(client, level: str | None = "editor") -> Municipality:
    municipality = complaints_member(level)
    login(client, EMAIL)
    return municipality


def _add(entity):
    with admin_session() as session, session.begin():
        session.add(entity)
    return entity


def make_area(municipality, name="Alumbrado Público") -> Area:
    return _add(Area(municipality_id=municipality.id, name=name))


def make_zone(municipality, name="Centro") -> Zone:
    return _add(Zone(municipality_id=municipality.id, name=name))


def make_type(municipality, area=None, name="Luminaria apagada", target_days=5, **fields):
    area = area or make_area(municipality, f"Área de {name}")
    return _add(
        ComplaintType(
            municipality_id=municipality.id,
            name=name,
            area_id=area.id,
            target_days=target_days,
            **fields,
        )
    )


def make_holiday(municipality, day: date, name="Feriado") -> Holiday:
    return _add(Holiday(municipality_id=municipality.id, date=day, name=name))


def set_weekdays(municipality, weekdays: list[int]) -> WorkingWeek:
    return _add(WorkingWeek(municipality_id=municipality.id, weekdays=weekdays))


def make_person(municipality, first="Lucía", last="Fernández", dni="33123456") -> Person:
    return _add(Person(municipality_id=municipality.id, first_name=first, last_name=last, dni=dni))


_numbers: dict = {}


def make_complaint(
    municipality,
    complaint_type: ComplaintType,
    zone: Zone,
    received_at: datetime,
    steps: list[tuple[datetime, str]] = (),
    address: str = "San Martín 100",
    area: Area | None = None,
    person: Person | None = None,
    target_days: int | None = None,
    number: int | None = None,
) -> Complaint:
    """A complaint with its history: created at `received_at`, then each (moment, state)."""
    state = steps[-1][1] if steps else "received"
    if number is None:
        number = _numbers.get(municipality.id, 0) + 1
    _numbers[municipality.id] = number
    area_id = area.id if area else complaint_type.area_id
    complaint = Complaint(
        municipality_id=municipality.id,
        number=number,
        type_id=complaint_type.id,
        area_id=area_id,
        zone_id=zone.id,
        address=address,
        person_id=person.id if person else None,
        state=state,
        target_days=target_days or complaint_type.target_days,
        received_at=received_at,
    )
    with admin_session() as session, session.begin():
        session.add(complaint)
        session.flush()
        events = [
            ComplaintEvent(
                kind="created",
                to_state="received",
                to_area_id=area_id,
                to_type_id=complaint_type.id,
                at=received_at,
            )
        ]
        previous = "received"
        for moment, to_state in steps:
            events.append(
                ComplaintEvent(kind="transition", from_state=previous, to_state=to_state, at=moment)
            )
            previous = to_state
        for position, event in enumerate(events):
            event.municipality_id = municipality.id
            event.complaint_id = complaint.id
            event.position = position
            session.add(event)
    return complaint


# Histories that leave a complaint in each state, all in the first week of March 2026.
HISTORIES: dict[str, list[tuple[datetime, str]]] = {
    "received": [],
    "assigned": [(at(2), "assigned")],
    "in_progress": [(at(2), "assigned"), (at(3), "in_progress")],
    "waiting": [(at(2), "assigned"), (at(3), "waiting")],
    "resolved": [(at(2), "assigned"), (at(3), "resolved")],
    "closed": [(at(2), "assigned"), (at(3), "resolved"), (at(4), "closed")],
    "rejected": [(at(2), "rejected")],
    "reopened": [(at(2), "assigned"), (at(3), "resolved"), (at(4), "reopened")],
}


class Setup:
    """One municipality's catalog: an area, a zone and a type routed to that area."""

    def __init__(self, municipality, target_days=5):
        self.municipality = municipality
        self.area = make_area(municipality)
        self.zone = make_zone(municipality)
        self.type = make_type(municipality, self.area, target_days=target_days)

    def complaint(self, state="received", received_at=None, **fields) -> Complaint:
        return make_complaint(
            self.municipality,
            self.type,
            self.zone,
            received_at or at(2, hour=9),
            HISTORIES[state],
            **fields,
        )
