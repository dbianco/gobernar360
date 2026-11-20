"""Builders for procedures-dashboard test data, written through the owner connection."""

from gobernar360.dashboards.procedures.models import (
    Area,
    Procedure,
    ProcedureRequirement,
    Requirement,
    Source,
)
from gobernar360.platform.models import Municipality
from tests.factories import admin_session, login, make_membership, make_municipality, make_user

BASE = "/api/dashboards/procedures"
EMAIL = "ana@noetinger.test"


def procedures_member(
    level: str | None = "editor",
    email: str = EMAIL,
    municipality: Municipality | None = None,
    municipality_name: str = "Noetinger",
) -> Municipality:
    """Create a user with that level on the procedures dashboard; return their municipality."""
    municipality = municipality or make_municipality(municipality_name)
    grants = {"procedures": level} if level else {}
    make_membership(make_user(email), municipality, grants=grants, enable=["procedures"])
    return municipality


def signed_in(client, level: str | None = "editor") -> Municipality:
    municipality = procedures_member(level)
    login(client, EMAIL)
    return municipality


def _add(entity):
    with admin_session() as session, session.begin():
        session.add(entity)
    return entity


def make_area(municipality, name="Rentas") -> Area:
    return _add(Area(municipality_id=municipality.id, name=name))


def make_source(municipality, name="Rentas municipal", level="municipal", area=None) -> Source:
    return _add(
        Source(
            municipality_id=municipality.id,
            name=name,
            level=level,
            area_id=area.id if area else None,
        )
    )


def make_requirement(municipality, name="Libre deuda municipal", source=None, **fields):
    return _add(
        Requirement(
            municipality_id=municipality.id,
            name=name,
            source_id=source.id if source else None,
            **fields,
        )
    )


def make_procedure(municipality, area=None, name="Habilitación comercial", **fields) -> Procedure:
    area = area or make_area(municipality, f"Área de {name}")
    defaults = {"audience": "both", "channel": "in_person", "is_free": True, "is_active": True}
    return _add(
        Procedure(
            municipality_id=municipality.id, area_id=area.id, name=name, **(defaults | fields)
        )
    )


def link_requirement(procedure, requirement, mandatory=True, format="paper", note=""):
    return _add(
        ProcedureRequirement(
            municipality_id=procedure.municipality_id,
            procedure_id=procedure.id,
            requirement_id=requirement.id,
            mandatory=mandatory,
            format=format,
            note=note,
        )
    )
