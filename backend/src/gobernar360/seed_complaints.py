"""Demo complaints: several hundred made-up cases over the last twelve months.

Each case is simulated over the municipality's own calendar, the same one the service clock
uses: some are solved in time and some late, some wait for the resident, a few are
reassigned, rejected or reopened, some addresses complain again and again, and recent or
stuck cases stay open. Everything is generated from a fixed seed, relative to today.
"""

import random
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from gobernar360.dashboards.complaints.clock import Calendar
from gobernar360.dashboards.complaints.models import (
    Area,
    Complaint,
    ComplaintEvent,
    ComplaintType,
    Holiday,
    Zone,
)
from gobernar360.platform.clock import LOCAL_TIMEZONE
from gobernar360.platform.models import Person

AREAS = (
    "Alumbrado Público",
    "Higiene Urbana",
    "Obras Públicas",
    "Espacios Verdes",
    "Inspección General",
)
ZONES = ("Centro", "Norte", "Sur", "Este", "Oeste", "Zona rural")
# name, area, target business days, relative frequency, share solved within the target
TYPES = (
    ("Luminaria apagada", "Alumbrado Público", 3, 22, 0.82),
    ("Poste de alumbrado dañado", "Alumbrado Público", 10, 5, 0.7),
    ("Residuos no recolectados", "Higiene Urbana", 2, 18, 0.85),
    ("Microbasural", "Higiene Urbana", 5, 8, 0.65),
    ("Bache", "Obras Públicas", 15, 14, 0.5),
    ("Calle de tierra en mal estado", "Obras Públicas", 10, 7, 0.55),
    ("Pérdida de agua en la vía pública", "Obras Públicas", 3, 6, 0.7),
    ("Árbol caído o con riesgo", "Espacios Verdes", 5, 6, 0.75),
    ("Pedido de poda", "Espacios Verdes", 20, 6, 0.6),
    ("Ruidos molestos", "Inspección General", 7, 4, 0.7),
    ("Animales sueltos", "Inspección General", 5, 4, 0.7),
)
# Received only in the first months, then retired: it stays in the figures.
RETIRED_TYPE = ("Recolección de ramas (operativo de otoño)", "Higiene Urbana", 10)
# Streets of each zone; the rural zone uses named roads.
STREETS = {
    "Centro": ("San Martín", "Belgrano", "Rivadavia", "25 de Mayo"),
    "Norte": ("Sarmiento", "Mitre", "Italia", "España"),
    "Sur": ("Moreno", "Independencia", "Colón", "Urquiza"),
    "Este": ("9 de Julio", "Lavalle", "Alberdi"),
    "Oeste": ("Avenida Libertador", "Maipú", "Chacabuco"),
    "Zona rural": ("Camino a Saira", "Camino a Marcos Juárez", "Ruta 2 km"),
}
# Places that complain again and again: (type, zone, address).
HOT_SPOTS = (
    ("Luminaria apagada", "Centro", "San Martín 450"),
    ("Residuos no recolectados", "Sur", "Moreno 1120"),
    ("Bache", "Norte", "Sarmiento 780"),
    ("Microbasural", "Oeste", "Maipú 1500"),
    ("Pérdida de agua en la vía pública", "Este", "Lavalle 320"),
    ("Calle de tierra en mal estado", "Zona rural", "Camino a Saira 2300"),
)
# Made-up residents who complain; those whose document is already in the registry are reused.
COMPLAINANTS = (
    ("Lucía", "Fernández", "33123456"),
    ("Diego", "Sosa", "36987654"),
    ("Rosa", "Aguirre", "24444444"),
    ("Norma", "Moyano", "16222333"),
    ("Marcos", "Giménez", "28888888"),
    ("Héctor", "Bustos", "14567321"),
    ("Graciela", "Peralta", "17890234"),
    ("Raúl", "Ledesma", "20345678"),
    ("Silvia", "Quiroga", "21456789"),
    ("Oscar", "Villarreal", "18234567"),
    ("Marta", "Ríos", "13678901"),
    ("Jorge", "Cabrera", "22567890"),
    ("Claudia", "Ferreyra", "23678901"),
    ("Walter", "Luna", "25789012"),
    ("Patricia", "Molina", "26890123"),
    ("Gustavo", "Ortiz", "27901234"),
    ("Mónica", "Herrera", "29012345"),
    ("Daniel", "Paz", "30123456"),
    ("Andrea", "Castro", "31234567"),
    ("Sergio", "Vera", "32345678"),
    ("Verónica", "Ojeda", "34456789"),
    ("Pablo", "Acosta", "35567890"),
    ("Carolina", "Medina", "37678901"),
    ("Martín", "Godoy", "38789012"),
    ("Natalia", "Domínguez", "39890123"),
    ("Ezequiel", "Navarro", "41901234"),
    ("Florencia", "Suárez", "42012345"),
    ("Ramón", "Correa", "11789456"),
    ("Elsa", "Figueroa", "12890567"),
    ("Alberto", "Sánchez", "15901678"),
)
NOTES = {
    "assigned": ("", "", "Derivado al área.", "Se asignó a la cuadrilla de turno."),
    "in_progress": ("", "Cuadrilla en camino.", "Se programó la visita.", "Trabajo iniciado."),
    "waiting": (
        "Se pidió al vecino la altura exacta.",
        "No se encontró a nadie en el domicilio; se dejó aviso.",
        "Se pidió al vecino una foto del problema.",
    ),
    "back": ("El vecino respondió.", "El vecino envió los datos.", "Se coordinó la visita."),
    "resolved": (
        "Trabajo terminado.",
        "Se resolvió en el lugar.",
        "Reparación realizada.",
        "Se verificó y quedó solucionado.",
    ),
    "closed": ("", "El vecino confirmó la solución.", "Cierre sin observaciones."),
    "rejected": (
        "Duplicado de otro reclamo abierto.",
        "Corresponde a la cooperativa de servicios, no al municipio.",
        "No se encontró el problema en la dirección indicada.",
    ),
    "reopened": (
        "El vecino informa que el problema persiste.",
        "Volvió a ocurrir a los pocos días.",
    ),
    "reassigned": ("Corresponde a otra área.", "Se deriva por competencia."),
}
DESCRIPTIONS = {
    "Luminaria apagada": "La luminaria de la esquina no enciende desde hace días.",
    "Poste de alumbrado dañado": "El poste está inclinado después de la tormenta.",
    "Residuos no recolectados": "No pasó el recolector en los últimos días.",
    "Microbasural": "Se acumula basura en el terreno baldío.",
    "Bache": "Bache grande en la calzada, peligroso para motos.",
    "Calle de tierra en mal estado": "La calle quedó intransitable después de la lluvia.",
    "Pérdida de agua en la vía pública": "Sale agua de la vereda de forma constante.",
    "Árbol caído o con riesgo": "Rama grande a punto de caer sobre los cables.",
    "Pedido de poda": "Pide poda del árbol de la vereda.",
    "Ruidos molestos": "Ruidos fuertes por las noches.",
    "Animales sueltos": "Perros sueltos en la cuadra.",
}
TARGET_COMPLAINTS = 420
SEED = 360


def easter(year: int) -> date:
    """Western Easter Sunday (anonymous Gregorian algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = divmod(b, 4)
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    week = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * week) // 451
    month, day = divmod(h + week - 7 * m + 114, 31)
    return date(year, month, day + 1)


def national_holidays(year: int) -> list[tuple[date, str]]:
    """Argentina's national holidays of a year, without the movable-bridge adjustments."""
    sunday = easter(year)
    return [
        (date(year, 1, 1), "Año Nuevo"),
        (sunday - timedelta(days=48), "Carnaval"),
        (sunday - timedelta(days=47), "Carnaval"),
        (date(year, 3, 24), "Día Nacional de la Memoria por la Verdad y la Justicia"),
        (date(year, 4, 2), "Día del Veterano y de los Caídos en Malvinas"),
        (sunday - timedelta(days=2), "Viernes Santo"),
        (date(year, 5, 1), "Día del Trabajador"),
        (date(year, 5, 25), "Día de la Revolución de Mayo"),
        (date(year, 6, 17), "Paso a la Inmortalidad del General Güemes"),
        (date(year, 6, 20), "Paso a la Inmortalidad del General Belgrano"),
        (date(year, 7, 9), "Día de la Independencia"),
        (date(year, 8, 17), "Paso a la Inmortalidad del General San Martín"),
        (date(year, 10, 12), "Día del Respeto a la Diversidad Cultural"),
        (date(year, 11, 20), "Día de la Soberanía Nacional"),
        (date(year, 12, 8), "Inmaculada Concepción de María"),
        (date(year, 12, 25), "Navidad"),
    ]


@dataclass
class Plan:
    """One simulated case before it is written: its reception and the steps after it."""

    type_name: str
    zone: str
    address: str
    received: datetime
    # (moment, kind, to_state or area name, note)
    steps: list[tuple[datetime, str, str, str]]


class _Simulation:
    def __init__(self, rng: random.Random, calendar: Calendar, now: datetime):
        self.rng = rng
        self.calendar = calendar
        self.now = now

    def moment(self, day: date, after: datetime | None = None) -> datetime:
        """Some time of the working day, later than `after` when it falls on the same day."""
        start = time(8, 0)
        if after is not None and after.date() == day:
            start = (after + timedelta(minutes=20)).time()
        minutes = start.hour * 60 + start.minute + self.rng.randint(0, 240)
        minutes = min(minutes, 23 * 60 + 50)
        return datetime.combine(day, time(minutes // 60, minutes % 60), LOCAL_TIMEZONE)

    def later(self, day: date, business_days: int) -> date:
        return self.calendar.add_business_days(day, business_days)

    def plan(
        self,
        type_name: str,
        target: int,
        on_time_share: float,
        area: str,
        zone: str,
        address: str,
        received: datetime,
    ) -> Plan:
        rng, cal = self.rng, self.calendar
        steps: list[tuple[datetime, str, str, str]] = []
        last = received

        def step(day: date, kind: str, value: str, note_key: str | None = None) -> None:
            nonlocal last
            at = self.moment(max(day, last.date()), last)
            note = rng.choice(NOTES[note_key or value]) if (note_key or value) in NOTES else ""
            steps.append((at, kind, value, note))
            last = at

        day0 = received.date()
        if rng.random() < 0.06:
            step(self.later(day0, rng.randint(0, 2)), "transition", "rejected")
            return Plan(type_name, zone, address, received, steps)
        assigned_on = self.later(day0, rng.choice((0, 0, 1)))
        step(assigned_on, "transition", "assigned")
        if rng.random() < 0.05:
            other = rng.choice([name for name in AREAS if name != area])
            step(assigned_on, "reassigned", other, "reassigned")
        # A few cases get stuck and swell the backlog.
        stuck = rng.random() < 0.05
        started_on = self.later(assigned_on, rng.choice((0, 1, 1, 2)))
        skip_start = rng.random() < 0.2
        if not skip_start:
            step(started_on, "transition", "in_progress")
        if stuck:
            return Plan(type_name, zone, address, received, steps)

        used_goal = (
            rng.randint(1, target)
            if rng.random() < on_time_share
            else rng.randint(target + 1, target * 2 + 3)
        )
        resume = day0
        used = 0
        if not skip_start and rng.random() < 0.15:
            wait_on = self.later(started_on, 1)
            used = cal.business_days_between(day0, wait_on)
            step(wait_on, "transition", "waiting")
            resume = self.later(wait_on, rng.randint(2, 6))
            step(resume, "transition", "in_progress", "back")
        resolved_on = self.later(resume, max(used_goal - used, 1))
        resolved_on = max(resolved_on, last.date())
        step(resolved_on, "transition", "resolved")
        if rng.random() < 0.05:
            reopened_on = self.later(resolved_on, rng.randint(2, 7))
            step(reopened_on, "transition", "reopened")
            step(self.later(reopened_on, rng.randint(1, 5)), "transition", "resolved")
        if rng.random() < 0.75:
            step(self.later(last.date(), rng.randint(2, 6)), "transition", "closed")
        return Plan(type_name, zone, address, received, steps)


def _address(rng: random.Random, zone: str) -> str:
    street = rng.choice(STREETS[zone])
    if street == "Ruta 2 km":
        return f"{street} {rng.randint(3, 18)}"
    return f"{street} {rng.randrange(100, 2000, 10)}"


def _reception(rng: random.Random, day: date) -> datetime:
    # Most complaints arrive in office hours; some come in online at night.
    hour = rng.randint(7, 13) if rng.random() < 0.8 else rng.randint(17, 22)
    return datetime.combine(day, time(hour, rng.randint(0, 59)), LOCAL_TIMEZONE)


def plan_complaints(
    calendar: Calendar, start: date, now: datetime, count: int, rng: random.Random
) -> list[Plan]:
    """Receptions spread over [start, today], each with its simulated history up to now."""
    sim = _Simulation(rng, calendar, now)
    types = {name: (area, target, share) for name, area, target, _, share in TYPES}
    weights = [weight for *_, weight, _ in TYPES]
    names = [name for name, *_ in TYPES]
    span = (now.date() - start).days
    plans = []
    for _ in range(count):
        day = start + timedelta(days=rng.randint(0, span))
        if not calendar.is_business_day(day) and rng.random() < 0.6:
            day = calendar.add_business_days(day, 1)
        received = _reception(rng, min(day, now.date()))
        if received > now:
            received = now - timedelta(minutes=rng.randint(5, 300))
        if rng.random() < 0.12:
            type_name, zone, address = rng.choice(HOT_SPOTS)
        else:
            type_name = rng.choices(names, weights)[0]
            zone = rng.choice(ZONES)
            address = _address(rng, zone)
        area, target, share = types[type_name]
        plans.append(sim.plan(type_name, target, share, area, zone, address, received))
    # The retired type, only in the first three months.
    for _ in range(8):
        received = _reception(rng, start + timedelta(days=rng.randint(0, 80)))
        name, area, target = RETIRED_TYPE
        zone = rng.choice(ZONES[:5])
        plans.append(sim.plan(name, target, 0.7, area, zone, _address(rng, zone), received))
    plans.sort(key=lambda plan: plan.received)
    # The newest one has just come in, whatever the moment the demo is loaded: nobody has
    # looked at it yet, so the demo always shows a complaint in every state.
    plans[-1].steps.clear()
    return plans


def seed_complaints(
    db: Session,
    municipality_id: uuid.UUID,
    users: list[uuid.UUID | None],
    now: datetime | None = None,
    count: int = TARGET_COMPLAINTS,
) -> None:
    """Catalog, holidays and `count` simulated complaints for one municipality.

    Nothing is dated after `now` (the current moment in Argentina by default).
    """
    rng = random.Random(SEED)
    now = now or datetime.now(LOCAL_TIMEZONE)
    today = now.date()

    def add(entity):
        entity.municipality_id = municipality_id
        db.add(entity)
        return entity

    areas = {name: add(Area(id=uuid.uuid4(), name=name)) for name in AREAS}
    zones = {name: add(Zone(id=uuid.uuid4(), name=name)) for name in ZONES}
    types = {
        name: add(
            ComplaintType(id=uuid.uuid4(), name=name, area_id=areas[area].id, target_days=target)
        )
        for name, area, target, _, _ in TYPES
    }
    name, area, target = RETIRED_TYPE
    types[name] = add(
        ComplaintType(
            id=uuid.uuid4(),
            name=name,
            area_id=areas[area].id,
            target_days=target,
            is_active=False,
        )
    )
    holidays = {
        day: label
        for year in (today.year - 1, today.year, today.year + 1)
        for day, label in national_holidays(year)
    }
    for day, label in sorted(holidays.items()):
        add(Holiday(date=day, name=label))
    db.flush()

    people = []
    for first, last, dni in COMPLAINANTS:
        person = db.scalar(select(Person).where(Person.dni == dni))
        if person is None:
            person = add(Person(id=uuid.uuid4(), first_name=first, last_name=last, dni=dni))
        people.append(person)
    db.flush()

    calendar = Calendar(holidays=frozenset(holidays))
    index = today.year * 12 + today.month - 1 - 11
    start = date(index // 12, index % 12 + 1, 1)
    for number, plan in enumerate(plan_complaints(calendar, start, now, count, rng), start=1):
        complaint_type = types[plan.type_name]
        area_id = complaint_type.area_id
        happened = [step for step in plan.steps if step[0] <= now]
        state = "received"
        complaint_id = uuid.uuid4()
        events = [
            ComplaintEvent(
                kind="created",
                to_state="received",
                to_area_id=area_id,
                to_type_id=complaint_type.id,
                at=plan.received,
                user_id=rng.choice(users),
            )
        ]
        for at, kind, value, note in happened:
            event = ComplaintEvent(kind=kind, at=at, note=note, user_id=rng.choice(users))
            if kind == "reassigned":
                event.from_area_id, area_id = area_id, areas[value].id
                event.to_area_id = area_id
            else:
                event.from_state, event.to_state, state = state, value, value
            events.append(event)
        anonymous = rng.random() < 0.4
        add(
            Complaint(
                id=complaint_id,
                number=number,
                type_id=complaint_type.id,
                area_id=area_id,
                zone_id=zones[plan.zone].id,
                address=plan.address,
                description=DESCRIPTIONS.get(plan.type_name, ""),
                person_id=None if anonymous else rng.choice(people).id,
                state=state,
                target_days=complaint_type.target_days,
                received_at=plan.received,
                created_by=events[0].user_id,
                updated_by=events[-1].user_id,
                created_at=plan.received,
                updated_at=events[-1].at,
            )
        )
        db.flush()
        for position, event in enumerate(events):
            event.complaint_id = complaint_id
            event.position = position
            add(event)
    db.flush()


# A small, separate catalog for the second municipality, so isolation can be seen.
COMMUNE_AREA = "Servicios Públicos"
COMMUNE_ZONES = ("Pueblo", "Zona rural")
COMMUNE_TYPES = (("Luminaria apagada", 3), ("Camino rural intransitable", 10))
COMMUNE_COMPLAINTS = (
    ("Luminaria apagada", "Pueblo", "Calle 5 n.º 230", 2, ()),
    ("Luminaria apagada", "Pueblo", "Calle 9 n.º 110", 6, ("assigned", "resolved", "closed")),
    ("Camino rural intransitable", "Zona rural", "Camino vecinal 12", 9, ("assigned",)),
    ("Camino rural intransitable", "Zona rural", "Camino vecinal 4", 20, ("assigned", "resolved")),
)


def seed_commune_complaints(
    db: Session, municipality_id: uuid.UUID, today: date, user_id: uuid.UUID
) -> None:
    def add(entity):
        entity.municipality_id = municipality_id
        db.add(entity)
        db.flush()
        return entity

    area = add(Area(name=COMMUNE_AREA))
    zones = {name: add(Zone(name=name)) for name in COMMUNE_ZONES}
    types = {
        name: add(ComplaintType(name=name, area_id=area.id, target_days=target))
        for name, target in COMMUNE_TYPES
    }
    for number, (type_name, zone, address, days_ago, states) in enumerate(
        COMMUNE_COMPLAINTS, start=1
    ):
        received = datetime.combine(today - timedelta(days=days_ago), time(9), LOCAL_TIMEZONE)
        complaint = add(
            Complaint(
                number=number,
                type_id=types[type_name].id,
                area_id=area.id,
                zone_id=zones[zone].id,
                address=address,
                state=states[-1] if states else "received",
                target_days=types[type_name].target_days,
                received_at=received,
            )
        )
        previous = "received"
        add(
            ComplaintEvent(
                complaint_id=complaint.id,
                position=0,
                kind="created",
                to_state=previous,
                to_area_id=area.id,
                to_type_id=types[type_name].id,
                at=received,
                user_id=user_id,
            )
        )
        for position, state in enumerate(states, start=1):
            add(
                ComplaintEvent(
                    complaint_id=complaint.id,
                    position=position,
                    kind="transition",
                    from_state=previous,
                    to_state=state,
                    at=received + timedelta(days=position),
                    user_id=user_id,
                )
            )
            previous = state
