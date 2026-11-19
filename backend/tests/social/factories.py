"""Builders for social-dashboard test data, written through the owner connection."""

from datetime import date

from gobernar360.dashboards.social.models import (
    Benefit,
    BenefitCategory,
    Delivery,
    Household,
    Intervention,
    InterventionType,
    SocialPerson,
)
from gobernar360.platform.models import Municipality, Person
from tests.factories import admin_session, make_membership, make_municipality, make_user

BASE = "/api/dashboards/social"
EMAIL = "ana@noetinger.test"


def social_member(
    level: str | None = "editor",
    email: str = EMAIL,
    municipality: Municipality | None = None,
    municipality_name: str = "Noetinger",
) -> Municipality:
    """Create a user with that level on the social dashboard; return their municipality."""
    municipality = municipality or make_municipality(municipality_name)
    grants = {"social": level} if level else {}
    make_membership(make_user(email), municipality, grants=grants, enable=["social"])
    return municipality


def _add(entity):
    with admin_session() as session, session.begin():
        session.add(entity)
    return entity


def make_benefit_category(municipality, name="Alimentos") -> BenefitCategory:
    return _add(BenefitCategory(municipality_id=municipality.id, name=name))


def make_benefit(municipality, category=None, name="Módulo alimentario", **fields) -> Benefit:
    category = category or make_benefit_category(municipality)
    return _add(
        Benefit(municipality_id=municipality.id, category_id=category.id, name=name, **fields)
    )


def make_intervention_type(municipality, name="Visita a domicilio") -> InterventionType:
    return _add(InterventionType(municipality_id=municipality.id, name=name))


def make_household(municipality, name="Familia Pérez", **fields) -> Household:
    return _add(Household(municipality_id=municipality.id, name=name, **fields))


def make_person(municipality, first_name="Juana", last_name="Pérez", **fields) -> Person:
    """A person in the municipality's registry, not yet incorporated by any dashboard."""
    return _add(
        Person(
            municipality_id=municipality.id, first_name=first_name, last_name=last_name, **fields
        )
    )


def make_social_person(
    municipality,
    first_name="Juana",
    last_name="Pérez",
    household=None,
    relationship=None,
    **fields,
) -> SocialPerson:
    person = make_person(municipality, first_name, last_name, **fields)
    if household is not None and relationship is None:
        relationship = "other_relative"
    return _add(
        SocialPerson(
            municipality_id=municipality.id,
            person_id=person.id,
            household_id=household.id if household else None,
            relationship=relationship,
        )
    )


def make_delivery(
    municipality, benefit, person, on=date(2026, 3, 10), quantity=1, note=""
) -> Delivery:
    return _add(
        Delivery(
            municipality_id=municipality.id,
            benefit_id=benefit.id,
            person_id=person.id,
            date=on,
            quantity=quantity,
            note=note,
        )
    )


def make_intervention(
    municipality,
    intervention_type,
    person,
    on=date(2026, 3, 10),
    description="",
    performed_by="",
) -> Intervention:
    return _add(
        Intervention(
            municipality_id=municipality.id,
            intervention_type_id=intervention_type.id,
            person_id=person.id,
            date=on,
            description=description,
            performed_by=performed_by,
        )
    )
