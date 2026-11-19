"""Builders for economic-dashboard test data, written through the owner connection."""

from datetime import date

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
from gobernar360.platform.models import Municipality, Person
from tests.factories import admin_session, make_membership, make_municipality, make_user

BASE = "/api/dashboards/economic"
EMAIL = "ana@noetinger.test"


def economic_member(
    level: str | None = "editor",
    email: str = EMAIL,
    municipality: Municipality | None = None,
    municipality_name: str = "Noetinger",
) -> Municipality:
    """Create a user with that level on the economic dashboard; return their municipality."""
    municipality = municipality or make_municipality(municipality_name)
    grants = {"economic": level} if level else {}
    make_membership(make_user(email), municipality, grants=grants, enable=["economic"])
    return municipality


def _add(entity):
    with admin_session() as session, session.begin():
        session.add(entity)
    return entity


def make_actor_type(municipality, name="Comercio") -> ActorType:
    return _add(ActorType(municipality_id=municipality.id, name=name))


def make_sector(municipality, name="Alimentos") -> Sector:
    return _add(Sector(municipality_id=municipality.id, name=name))


def make_tool_category(municipality, name="Financiamiento") -> ToolCategory:
    return _add(ToolCategory(municipality_id=municipality.id, name=name))


def make_tool_subcategory(municipality, category=None, name="Microcréditos") -> ToolSubcategory:
    category = category or make_tool_category(municipality)
    return _add(
        ToolSubcategory(municipality_id=municipality.id, category_id=category.id, name=name)
    )


def make_tool(
    municipality, category=None, name="Microcrédito productivo", audience="both", **fields
) -> Tool:
    category = category or make_tool_category(municipality)
    return _add(
        Tool(
            municipality_id=municipality.id,
            category_id=category.id,
            name=name,
            audience=audience,
            **fields,
        )
    )


def make_actor(municipality, name="Panadería La Espiga", **fields) -> Actor:
    return _add(Actor(municipality_id=municipality.id, name=name, **fields))


def make_person(municipality, first_name="Juana", last_name="Pérez", **fields) -> Person:
    """A person in the municipality's registry, not yet incorporated by any dashboard."""
    return _add(
        Person(
            municipality_id=municipality.id, first_name=first_name, last_name=last_name, **fields
        )
    )


def make_economic_person(
    municipality,
    first_name="Juana",
    last_name="Pérez",
    employment_status="unknown",
    occupation="",
    **fields,
) -> EconomicPerson:
    person = make_person(municipality, first_name, last_name, **fields)
    return _add(
        EconomicPerson(
            municipality_id=municipality.id,
            person_id=person.id,
            employment_status=employment_status,
            occupation=occupation,
        )
    )


def make_actor_person(municipality, actor, person, role="owner") -> ActorPerson:
    return _add(
        ActorPerson(
            municipality_id=municipality.id, actor_id=actor.id, person_id=person.id, role=role
        )
    )


def make_assignment(
    municipality, tool, actor=None, person=None, on=date(2026, 3, 10), note=""
) -> Assignment:
    return _add(
        Assignment(
            municipality_id=municipality.id,
            tool_id=tool.id,
            actor_id=actor.id if actor else None,
            person_id=person.id if person else None,
            date=on,
            note=note,
        )
    )
