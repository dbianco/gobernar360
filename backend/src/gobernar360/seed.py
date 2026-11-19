"""Demo data: two municipalities with users of every role and populated dashboards.

For local development, demos and end-to-end tests only: every account shares a known password.
"""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from gobernar360.core.db import Base, get_admin_engine, platform_session, tenant_session
from gobernar360.core.security import hash_password
from gobernar360.dashboards.economic.models import (
    Actor,
    ActorPerson,
    ActorType,
    Assignment,
    EconomicPerson,
    Sector,
    Tool,
    ToolCategory,
    ToolSubcategory,
)
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
    Person,
    User,
)

DEMO_PASSWORD = "gobernar360-demo"
PROJECTS = "projects"
ENVIRONMENT = "environment"
ECONOMIC = "economic"

ECONOMIC_ACTOR_TYPES = ("Comercio", "Industria", "Emprendimiento", "Servicios", "Cooperativa")
ECONOMIC_SECTORS = ("Alimentos", "Metalmecánica", "Textil", "Agro", "Turismo", "Construcción")
# category -> subcategory (None: directly under the category) -> tools as (name, audience,
# description).
ECONOMIC_TOOLS = {
    "Financiamiento": {
        "Microcréditos": [
            ("Microcrédito productivo", "both", "Hasta $ 1.500.000 a tasa subsidiada."),
        ],
        "Subsidios": [
            ("Subsidio de tasa para inversión", "actors", "Bonificación de tasa bancaria."),
        ],
    },
    "Capacitación": {
        "Gestión": [
            ("Curso de costos y precios", "both", "Cuatro encuentros presenciales."),
        ],
        "Oficios": [
            ("Taller de oficios", "people", "Electricidad, soldadura y gastronomía."),
        ],
    },
    "Empleo": {
        None: [
            ("Bolsa de empleo municipal", "people", "Intermediación con empresas locales."),
        ],
    },
    "Comercialización": {
        "Ferias": [
            ("Feria de emprendedores", "actors", "Puesto en la feria mensual de la plaza."),
        ],
    },
}
# (name, type, sector, CUIT, employees, address)
ECONOMIC_ACTORS = [
    ("Panadería La Espiga", "Comercio", "Alimentos", "30711111118", 6, "San Martín 245"),
    ("Metalúrgica Noetinger SRL", "Industria", "Metalmecánica", "30722222226", 38, "Ruta 2 km 4"),
    ("Agroservicios del Centro", "Servicios", "Agro", "30733333334", 12, "Av. Centenario 810"),
    ("Tejidos Doña Rosa", "Emprendimiento", "Textil", "27244444442", 1, "Belgrano 132"),
    ("Cooperativa de Trabajo El Molino", "Cooperativa", "Alimentos", "30755555550", 21, ""),
    ("Hospedaje Los Aromos", "Servicios", "Turismo", "", 4, "Bv. Argentino 55"),
    ("Corralón Sarmiento", "Comercio", "Construcción", "30777777776", 9, "Sarmiento 990"),
    ("Dulces del Monte", "Emprendimiento", "Alimentos", "", 2, "Zona rural"),
    ("Tornería Giménez", "Industria", "Metalmecánica", "20288888883", 5, "Parque industrial"),
    ("Almacén Don Pepe", "Comercio", "Alimentos", "", None, "Rivadavia 410"),
    ("Estudio Contable Rivas", "Servicios", None, "", 3, "25 de Mayo 78"),
    ("Vivero El Ceibo", None, "Agro", "", 2, "Camino a Saira"),
]
# (first name, last name, DNI, year of birth, neighborhood, employment status, occupation)
ECONOMIC_PEOPLE = [
    ("Rosa", "Aguirre", "24444444", 1975, "Centro", "self_employed", "Tejedora"),
    ("Marcos", "Giménez", "28888888", 1981, "Norte", "self_employed", "Tornero"),
    ("Lucía", "Fernández", "33123456", 1988, "Centro", "employed", "Administrativa"),
    ("Diego", "Sosa", "36987654", 1992, "Sur", "unemployed", "Soldador"),
    ("Paula", "Rivas", "27456123", 1979, "Centro", "self_employed", "Contadora"),
    ("Julián", "Moyano", "40111222", 1997, "Oeste", "unemployed", ""),
    ("Carla", "Benítez", "41222333", 1998, "Norte", "student", "Estudiante de gastronomía"),
    ("Hugo", "Peralta", "17555666", 1965, "Sur", "employed", "Panadero"),
    ("Mirta", "Domínguez", "14333222", 1960, "Centro", "retired", "Docente jubilada"),
    ("Nicolás", "Ortiz", "38777111", 1994, "Oeste", "employed", "Operario"),
    ("Valeria", "Luna", "35666999", 1990, "Norte", "self_employed", "Productora de dulces"),
    ("Sergio", "Acosta", None, None, "Zona rural", "unknown", ""),
    ("Elena", "Paz", "30222111", 1983, "Sur", "other", "Cuidadora"),
    ("Tomás", "Herrera", "42999000", 2000, "Centro", "student", ""),
]
# (actor, person as "first last", role)
ECONOMIC_LINKS = [
    ("Tejidos Doña Rosa", "Rosa Aguirre", "owner"),
    ("Tornería Giménez", "Marcos Giménez", "owner"),
    ("Estudio Contable Rivas", "Paula Rivas", "owner"),
    ("Panadería La Espiga", "Hugo Peralta", "employee"),
    ("Metalúrgica Noetinger SRL", "Nicolás Ortiz", "employee"),
    ("Metalúrgica Noetinger SRL", "Lucía Fernández", "contact"),
    ("Dulces del Monte", "Valeria Luna", "owner"),
]
# (tool, recipient, days before today; None: a fixed date last year as (month, day))
ECONOMIC_ASSIGNMENTS = [
    ("Microcrédito productivo", "Panadería La Espiga", 20, None),
    ("Microcrédito productivo", "Tejidos Doña Rosa", 75, None),
    ("Microcrédito productivo", "Dulces del Monte", 140, None),
    ("Subsidio de tasa para inversión", "Metalúrgica Noetinger SRL", 45, None),
    ("Subsidio de tasa para inversión", "Tornería Giménez", None, (9, 12)),
    ("Curso de costos y precios", "Tejidos Doña Rosa", 30, None),
    ("Curso de costos y precios", "Almacén Don Pepe", 30, None),
    ("Curso de costos y precios", "Dulces del Monte", 30, None),
    ("Feria de emprendedores", "Tejidos Doña Rosa", 10, None),
    ("Feria de emprendedores", "Dulces del Monte", 10, None),
    ("Feria de emprendedores", "Vivero El Ceibo", 100, None),
    ("Feria de emprendedores", "Tejidos Doña Rosa", None, (11, 8)),
    ("Microcrédito productivo", "Corralón Sarmiento", None, (5, 20)),
    ("Taller de oficios", "Diego Sosa", 60, None),
    ("Taller de oficios", "Julián Moyano", 60, None),
    ("Taller de oficios", "Carla Benítez", 60, None),
    ("Taller de oficios", "Tomás Herrera", None, (8, 3)),
    ("Bolsa de empleo municipal", "Diego Sosa", 15, None),
    ("Bolsa de empleo municipal", "Julián Moyano", 5, None),
    ("Bolsa de empleo municipal", "Elena Paz", 120, None),
    ("Bolsa de empleo municipal", "Nicolás Ortiz", None, (3, 14)),
    ("Curso de costos y precios", "Valeria Luna", 30, None),
    ("Curso de costos y precios", "Rosa Aguirre", 30, None),
    ("Microcrédito productivo", "Marcos Giménez", 200, None),
    ("Microcrédito productivo", "Valeria Luna", None, (10, 2)),
]

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


def _seed_noetinger_economic(municipality_id, today: date) -> None:
    """Actors, people, tools and assignments spread over this year and the last one."""
    with tenant_session(municipality_id) as db:

        def add(entity):
            entity.municipality_id = municipality_id
            db.add(entity)
            db.flush()
            return entity

        actor_types = {name: add(ActorType(name=name)) for name in ECONOMIC_ACTOR_TYPES}
        sectors = {name: add(Sector(name=name)) for name in ECONOMIC_SECTORS}
        tools = {}
        for category_name, subcategories in ECONOMIC_TOOLS.items():
            category = add(ToolCategory(name=category_name))
            for subcategory_name, rows in subcategories.items():
                subcategory = subcategory_name and add(
                    ToolSubcategory(category_id=category.id, name=subcategory_name)
                )
                for name, audience, description in rows:
                    tools[name] = add(
                        Tool(
                            category_id=category.id,
                            subcategory_id=subcategory.id if subcategory else None,
                            name=name,
                            audience=audience,
                            description=description,
                        )
                    )
        actors = {}
        for name, actor_type, sector, cuit, employees, address in ECONOMIC_ACTORS:
            actors[name] = add(
                Actor(
                    name=name,
                    actor_type_id=actor_types[actor_type].id if actor_type else None,
                    sector_id=sectors[sector].id if sector else None,
                    cuit=cuit,
                    employee_count=employees,
                    address=address,
                )
            )
        people = {}
        for first, last, dni, born, neighborhood, status, occupation in ECONOMIC_PEOPLE:
            person = add(
                Person(
                    first_name=first,
                    last_name=last,
                    dni=dni,
                    birth_date=date(born, 6, 15) if born else None,
                    neighborhood=neighborhood,
                )
            )
            people[f"{first} {last}"] = add(
                EconomicPerson(person_id=person.id, employment_status=status, occupation=occupation)
            )
        for actor, person, role in ECONOMIC_LINKS:
            add(ActorPerson(actor_id=actors[actor].id, person_id=people[person].id, role=role))
        start_of_year = date(today.year, 1, 1)
        for tool, recipient, days_ago, last_year in ECONOMIC_ASSIGNMENTS:
            if last_year:
                on = date(today.year - 1, *last_year)
            else:
                # Early in the year "days ago" would fall in the previous one.
                on = max(today - timedelta(days=days_ago), start_of_year)
            add(
                Assignment(
                    tool_id=tools[tool].id,
                    actor_id=actors[recipient].id if recipient in actors else None,
                    person_id=people[recipient].id if recipient in people else None,
                    date=on,
                )
            )


def _enable_dashboard(db: Session, municipality: Municipality, key: str) -> bool:
    """Enable a newer dashboard and give it to whoever has the projects one.

    Returns False when it was already enabled, so older demo databases gain the
    dashboard once and are otherwise left alone.
    """
    if db.get(MunicipalityDashboard, (municipality.id, key)):
        return False
    db.add(MunicipalityDashboard(municipality_id=municipality.id, dashboard_key=key))
    memberships = db.scalars(
        select(Membership).where(Membership.municipality_id == municipality.id)
    ).unique()
    for membership in memberships:
        for grant in list(membership.grants):
            if grant.dashboard_key == PROJECTS:
                membership.grants.append(DashboardGrant(dashboard_key=key, level=grant.level))
    return True


def _seed_newer_dashboard(key: str, seed_noetinger, today: date) -> bool:
    """Add a dashboard that came after the first demo: enabled in both municipalities,
    with data only in Noetinger. Returns False when the demo already had it."""
    with platform_session() as db:
        noetinger = db.scalar(select(Municipality).where(Municipality.slug == "noetinger"))
        commune = db.scalar(select(Municipality).where(Municipality.slug == "comuna-demo"))
        added = _enable_dashboard(db, noetinger, key)
        # An older demo database may no longer have the second municipality.
        if commune is not None:
            _enable_dashboard(db, commune, key)
        noetinger_id = noetinger.id
    if added:
        seed_noetinger(noetinger_id, today)
    return added


def _seed_newer_dashboards(today: date) -> bool:
    added = [
        _seed_newer_dashboard(ENVIRONMENT, _seed_noetinger_environment, today),
        _seed_newer_dashboard(ECONOMIC, _seed_noetinger_economic, today),
    ]
    return any(added)


def seed_demo(reset: bool = False) -> bool:
    """Load the demo data. Returns False when it was already present and nothing changed."""
    if reset:
        _reset()
    today = date.today()
    with platform_session() as db:
        already_seeded = db.scalar(select(Municipality.id).where(Municipality.slug == "noetinger"))
    if already_seeded:
        # Only add what newer versions of the demo bring.
        return _seed_newer_dashboards(today)
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
    _seed_newer_dashboards(today)
    return True
