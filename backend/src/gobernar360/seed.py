"""Demo data: two municipalities with users of every role and populated dashboards.

For local development, demos and end-to-end tests only: every account shares a known password.
"""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from gobernar360.core.db import Base, get_admin_engine, platform_session, tenant_session
from gobernar360.core.security import hash_password
from gobernar360.dashboards.environment.models import Subcategory, Value, Variable
from gobernar360.dashboards.projects.models import (
    AnnualBudget,
    Axis,
    Department,
    Indicator,
    Milestone,
    Objective,
    Owner,
    Program,
    Project,
    ProjectSdg,
    Term,
)
from gobernar360.platform.models import (
    DashboardGrant,
    Membership,
    Municipality,
    MunicipalityDashboard,
    User,
)

DEMO_PASSWORD = "gobernar360-demo"
PROJECTS = "projects"
ENVIRONMENT = "environment"

# category -> subcategory -> variables as (name, unit, frequency, aggregation, direction,
# source, target, typical value per period). Air is left empty on purpose, to show how a
# category without variables looks.
ENVIRONMENT_VARIABLES = {
    "energy": {
        "Consumo eléctrico": [
            ("Consumo eléctrico de edificios municipales", "kWh", "monthly", "sum",
             "lower_is_better", "external", "420000", "33000"),
            ("Luminarias LED instaladas", "luminarias", "annual", "sum",
             "higher_is_better", "municipal", "1200", "1250"),
        ],
        "Energías renovables": [
            ("Energía solar generada", "kWh", "monthly", "sum",
             "higher_is_better", "municipal", "60000", "3500"),
        ],
    },
    "waste": {
        "Recolección": [
            ("Residuos enviados a disposición final", "t", "monthly", "sum",
             "lower_is_better", "municipal", "6000", "470"),
            ("Material reciclado recuperado", "t", "monthly", "sum",
             "higher_is_better", "municipal", "300", "22"),
        ],
        "Economía circular": [
            ("Cooperativas de recuperadores urbanos", "cooperativas", "annual", "sum",
             "higher_is_better", "municipal", None, "2"),
        ],
    },
    "water": {
        "Calidad del agua": [
            ("Muestras de agua aptas para consumo", "%", "monthly", "average",
             "higher_is_better", "external", "88", "90"),
        ],
        "Consumo": [
            ("Consumo de agua por habitante", "l/día", "monthly", "average",
             "lower_is_better", "external", "250", "265"),
        ],
    },
    "mobility": {
        "Movilidad sustentable": [
            ("Ciclovías habilitadas", "km", "annual", "sum",
             "higher_is_better", "municipal", "12", "8"),
        ],
    },
    "biodiversity": {
        "Arbolado urbano": [
            ("Árboles plantados", "árboles", "monthly", "sum",
             "higher_is_better", "municipal", "500", "55"),
        ],
    },
    "governance": {
        "Planificación": [
            # Never loaded: shows a variable the municipality is not measuring yet.
            ("Capacitaciones ambientales al personal", "capacitaciones", "annual", "sum",
             "higher_is_better", "municipal", None, None),
        ],
    },
}  # fmt: skip
# Month-to-month variation applied to the typical value, so charts are not flat.
SEASONALITY = (1.08, 1.04, 0.98, 0.95, 0.97, 1.05, 1.1, 1.06, 0.96, 0.93, 0.95, 1.02)

AXES = {
    "Ciudad con calidad de vida": ["Mejorar el espacio público", "Ampliar los servicios básicos"],
    "Ciudad inclusiva": ["Reducir el déficit habitacional", "Acompañar a las familias vulnerables"],
    "Ciudad segura": ["Mejorar la iluminación y el monitoreo"],
    "Modernización del Estado": ["Digitalizar los trámites municipales"],
}
DEPARTMENTS = [
    "Secretaría de Hacienda",
    "Obras Públicas",
    "Modernización",
    "Seguridad",
    "Salud y Medioambiente",
    "Gobierno y Coordinación",
]
PROGRAMS = ["Plan de obras 2023-2027", "Noetinger Digital", "Barrios seguros"]
OWNERS = ["María Pérez", "Juan Sosa", "Lucía Fernández", "Carlos Gómez"]

# (name, axis, objective index, department, owner, program, priority, year, status,
#  start offset days, end offset days, planned, executed, manual progress, SDGs,
#  milestones as (name, due offset days, completed offset days or None))
PROJECT_ROWS = [
    (
        "Pavimentación de la calle San Martín",
        "Ciudad con calidad de vida",
        0,
        "Obras Públicas",
        "María Pérez",
        "Plan de obras 2023-2027",
        "A+",
        0,
        "in_progress",
        -200,
        120,
        "85000000",
        "41000000",
        None,
        [9, 11],
        [
            ("Licitación adjudicada", -150, -160),
            ("Inicio de obra", -90, -85),
            ("Cordón cuneta terminado", 20, None),
            ("Habilitación", 110, None),
        ],
    ),
    (
        "Renovación de la plaza central",
        "Ciudad con calidad de vida",
        0,
        "Obras Públicas",
        "María Pérez",
        "Plan de obras 2023-2027",
        "A",
        0,
        "in_progress",
        -120,
        60,
        "32000000",
        "12500000",
        None,
        [11],
        [("Proyecto ejecutivo", -100, -95), ("Juegos y mobiliario instalados", -15, None)],
    ),
    (
        "Extensión de la red de cloacas barrio Norte",
        "Ciudad con calidad de vida",
        1,
        "Obras Públicas",
        "Juan Sosa",
        "Plan de obras 2023-2027",
        "A+",
        0,
        "in_progress",
        -300,
        -20,
        "120000000",
        "96000000",
        None,
        [6, 11],
        [("Primera etapa", -200, -190), ("Segunda etapa", -60, -40)],
    ),
    (
        "Planta de tratamiento de residuos",
        "Ciudad con calidad de vida",
        1,
        "Salud y Medioambiente",
        "Lucía Fernández",
        None,
        "B",
        1,
        "not_started",
        60,
        400,
        "64000000",
        "0",
        None,
        [12, 13],
        [],
    ),
    (
        "Lotes con servicios para primera vivienda",
        "Ciudad inclusiva",
        0,
        "Gobierno y Coordinación",
        "Carlos Gómez",
        None,
        "A",
        0,
        "in_progress",
        -180,
        200,
        "58000000",
        "17400000",
        30,
        [1, 11],
        [],
    ),
    (
        "Mejoramiento habitacional de 40 viviendas",
        "Ciudad inclusiva",
        0,
        "Obras Públicas",
        "Juan Sosa",
        None,
        "A",
        -1,
        "finished",
        -500,
        -200,
        "24000000",
        "23800000",
        None,
        [1, 11],
        [("Relevamiento social", -480, -470), ("Obras finalizadas", -210, -205)],
    ),
    (
        "Centro de atención a las familias",
        "Ciudad inclusiva",
        1,
        "Salud y Medioambiente",
        "Lucía Fernández",
        None,
        "B",
        0,
        "not_started",
        30,
        300,
        "18000000",
        "0",
        None,
        [3, 10],
        [("Definición del edificio", 45, None)],
    ),
    (
        "Recambio a luminarias LED",
        "Ciudad segura",
        0,
        "Obras Públicas",
        "María Pérez",
        "Barrios seguros",
        "A+",
        -1,
        "finished",
        -420,
        -150,
        "27000000",
        "26100000",
        None,
        [7, 11],
        [("Compra de luminarias", -400, -390), ("Instalación completa", -160, -155)],
    ),
    (
        "Centro de monitoreo y cámaras",
        "Ciudad segura",
        0,
        "Seguridad",
        "Carlos Gómez",
        "Barrios seguros",
        "A",
        0,
        "in_progress",
        -90,
        150,
        "45000000",
        "9000000",
        None,
        [16],
        [("Sala de monitoreo equipada", -30, None), ("20 cámaras instaladas", 90, None)],
    ),
    (
        "Ventanilla única digital de trámites",
        "Modernización del Estado",
        0,
        "Modernización",
        "Juan Sosa",
        "Noetinger Digital",
        "A",
        0,
        "in_progress",
        -150,
        90,
        "15000000",
        "6000000",
        None,
        [9, 16],
        [
            ("Relevamiento de trámites", -120, -118),
            ("Primeros 10 trámites en línea", -10, -5),
            ("Todos los trámites en línea", 80, None),
        ],
    ),
    (
        "Expediente electrónico",
        "Modernización del Estado",
        0,
        "Modernización",
        "Juan Sosa",
        "Noetinger Digital",
        "B",
        1,
        "not_started",
        120,
        480,
        "9000000",
        "0",
        None,
        [16],
        [],
    ),
    (
        "Portal de datos abiertos",
        "Modernización del Estado",
        0,
        "Gobierno y Coordinación",
        None,
        "Noetinger Digital",
        "C",
        0,
        "in_progress",
        -60,
        240,
        "3500000",
        "700000",
        20,
        [16, 17],
        [],
    ),
]


def _reset() -> None:
    tables = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    with get_admin_engine().begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


def _user(db: Session, email: str, full_name: str, operator: bool = False) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            email=email,
            full_name=full_name,
            password_hash=hash_password(DEMO_PASSWORD),
            is_platform_operator=operator,
        )
        db.add(user)
        db.flush()
    return user


def _municipality(db: Session, name: str, slug: str, kind: str) -> Municipality:
    municipality = Municipality(name=name, slug=slug, kind=kind)
    db.add(municipality)
    db.flush()
    db.add(MunicipalityDashboard(municipality_id=municipality.id, dashboard_key=PROJECTS))
    return municipality


def _member(
    db: Session,
    municipality: Municipality,
    email: str,
    full_name: str,
    admin: bool = False,
    level: str | None = None,
) -> None:
    membership = Membership(
        user_id=_user(db, email, full_name).id, municipality_id=municipality.id, is_admin=admin
    )
    if level:
        membership.grants = [DashboardGrant(dashboard_key=PROJECTS, level=level)]
    db.add(membership)


def _seed_noetinger_projects(municipality_id, today: date) -> None:
    with tenant_session(municipality_id) as db:

        def add(entity):
            entity.municipality_id = municipality_id
            db.add(entity)
            db.flush()
            return entity

        start_year = today.year - 1
        term = add(
            Term(
                name=f"Gestión {start_year}-{start_year + 4}",
                start_year=start_year,
                end_year=start_year + 4,
            )
        )
        for offset, amount in enumerate(["950000000", "1200000000", "1400000000"]):
            add(AnnualBudget(term_id=term.id, year=start_year + offset, total_amount=amount))

        axes, objectives = {}, {}
        for axis_name, objective_names in AXES.items():
            axes[axis_name] = add(Axis(term_id=term.id, name=axis_name))
            objectives[axis_name] = [
                add(Objective(axis_id=axes[axis_name].id, name=name)) for name in objective_names
            ]
        departments = {name: add(Department(name=name)) for name in DEPARTMENTS}
        programs = {name: add(Program(name=name)) for name in PROGRAMS}
        owners = {name: add(Owner(full_name=name)) for name in OWNERS}

        for row in PROJECT_ROWS:
            (name, axis, objective, department, owner, program, priority, year_offset, status,
             start, end, planned, executed, manual, sdgs, milestones) = row  # fmt: skip
            add(
                Project(
                    term_id=term.id,
                    name=name,
                    axis_id=axes[axis].id,
                    objective_id=objectives[axis][objective].id,
                    department_id=departments[department].id,
                    owner_id=owners[owner].id if owner else None,
                    program_id=programs[program].id if program else None,
                    priority=priority,
                    year=today.year + year_offset,
                    status=status,
                    start_date=today + timedelta(days=start),
                    end_date=today + timedelta(days=end),
                    planned_budget=Decimal(planned),
                    executed_budget=Decimal(executed),
                    manual_progress=manual,
                    sdgs=[ProjectSdg(municipality_id=municipality_id, sdg_number=n) for n in sdgs],
                    milestones=[
                        Milestone(
                            municipality_id=municipality_id,
                            name=milestone_name,
                            due_date=today + timedelta(days=due),
                            completed_on=None if done is None else today + timedelta(days=done),
                        )
                        for milestone_name, due, done in milestones
                    ],
                )
            )

        indicator_rows = [
            ("Ciudad con calidad de vida", 0, "Cuadras pavimentadas", "cuadras", 120, 200, 152),
            ("Ciudad con calidad de vida", 1, "Hogares con cloacas", "%", 62, 85, 74),
            ("Ciudad inclusiva", 0, "Familias con vivienda regularizada", "familias", 0, 120, 40),
            ("Ciudad segura", 0, "Luminarias LED instaladas", "luminarias", 300, 1400, 1400),
            ("Modernización del Estado", 0, "Trámites disponibles en línea", "trámites", 2, 45, 12),
        ]
        for axis, objective, name, unit, baseline, target, current in indicator_rows:
            add(
                Indicator(
                    objective_id=objectives[axis][objective].id,
                    name=name,
                    unit=unit,
                    baseline=baseline,
                    target=target,
                    current_value=current,
                )
            )


def _seed_commune_projects(municipality_id, today: date) -> None:
    with tenant_session(municipality_id) as db:

        def add(entity):
            entity.municipality_id = municipality_id
            db.add(entity)
            db.flush()
            return entity

        term = add(
            Term(name=f"Gestión {today.year}", start_year=today.year, end_year=today.year + 3)
        )
        axis = add(Axis(term_id=term.id, name="Servicios comunales"))
        department = add(Department(name="Presidencia comunal"))
        for name in ("Mejorado de caminos rurales", "Ampliación del dispensario"):
            add(
                Project(
                    term_id=term.id,
                    name=name,
                    axis_id=axis.id,
                    department_id=department.id,
                    priority="A",
                    year=today.year,
                    status="in_progress",
                    planned_budget=Decimal("5000000"),
                )
            )


def _seed_noetinger_environment(municipality_id, today: date) -> None:
    """Variables with last year complete and this year loaded up to last month."""
    with tenant_session(municipality_id) as db:

        def add(entity):
            entity.municipality_id = municipality_id
            db.add(entity)
            db.flush()
            return entity

        for category, subcategories in ENVIRONMENT_VARIABLES.items():
            for subcategory_name, rows in subcategories.items():
                subcategory = add(Subcategory(category=category, name=subcategory_name))
                for name, unit, frequency, aggregation, direction, source, target, typical in rows:
                    variable = add(
                        Variable(
                            subcategory_id=subcategory.id,
                            name=name,
                            unit=unit,
                            frequency=frequency,
                            annual_aggregation=aggregation,
                            direction=direction,
                            source=source,
                            target=Decimal(target) if target else None,
                        )
                    )
                    if typical is None:
                        continue
                    if frequency == "annual":
                        periods = [(today.year - 1, 0, Decimal("0.8")), (today.year, 0, Decimal(1))]
                    else:
                        periods = [
                            (year, month, Decimal(str(SEASONALITY[month - 1])))
                            for year, last_month in (
                                (today.year - 1, 12),
                                (today.year, today.month - 1),
                            )
                            for month in range(1, last_month + 1)
                        ]
                    for year, period, factor in periods:
                        value = (Decimal(typical) * factor).quantize(Decimal("0.01"))
                        add(Value(variable_id=variable.id, year=year, period=period, value=value))


def _enable_environment(db: Session, municipality: Municipality) -> bool:
    """Enable the environment dashboard and give it to whoever has the projects one.

    Returns False when it was already enabled, so older demo databases gain the
    dashboard once and are otherwise left alone.
    """
    if db.get(MunicipalityDashboard, (municipality.id, ENVIRONMENT)):
        return False
    db.add(MunicipalityDashboard(municipality_id=municipality.id, dashboard_key=ENVIRONMENT))
    memberships = db.scalars(
        select(Membership).where(Membership.municipality_id == municipality.id)
    ).unique()
    for membership in memberships:
        for grant in list(membership.grants):
            if grant.dashboard_key == PROJECTS:
                membership.grants.append(
                    DashboardGrant(dashboard_key=ENVIRONMENT, level=grant.level)
                )
    return True


def _seed_environment(today: date) -> bool:
    with platform_session() as db:
        noetinger = db.scalar(select(Municipality).where(Municipality.slug == "noetinger"))
        commune = db.scalar(select(Municipality).where(Municipality.slug == "comuna-demo"))
        added = _enable_environment(db, noetinger)
        # An older demo database may no longer have the second municipality.
        if commune is not None:
            _enable_environment(db, commune)
        noetinger_id = noetinger.id
    if added:
        _seed_noetinger_environment(noetinger_id, today)
    return added


def seed_demo(reset: bool = False) -> bool:
    """Load the demo data. Returns False when it was already present and nothing changed."""
    if reset:
        _reset()
    today = date.today()
    with platform_session() as db:
        already_seeded = db.scalar(select(Municipality.id).where(Municipality.slug == "noetinger"))
    if already_seeded:
        # Only add what newer versions of the demo bring.
        return _seed_environment(today)
    with platform_session() as db:
        _user(db, "operador@gobernar360.test", "Operador de la plataforma", operator=True)

        noetinger = _municipality(db, "Noetinger", "noetinger", "municipality")
        _member(db, noetinger, "admin@noetinger.test", "Ana Administradora", admin=True)
        _member(db, noetinger, "carga@noetinger.test", "Carla Carga", level="editor")
        _member(db, noetinger, "lectura@noetinger.test", "Leo Lectura", level="viewer")
        _member(db, noetinger, "sinacceso@noetinger.test", "Sofía Sin Acceso")

        commune = _municipality(db, "Comuna Demo", "comuna-demo", "commune")
        _member(db, commune, "admin@comuna-demo.test", "Andrés Administrador", admin=True)
        noetinger_id, commune_id = noetinger.id, commune.id

    _seed_noetinger_projects(noetinger_id, today)
    _seed_commune_projects(commune_id, today)
    _seed_environment(today)
    return True
