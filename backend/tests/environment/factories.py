"""Builders for environment-dashboard test data, written through the owner connection."""

from decimal import Decimal

from gobernar360.dashboards.environment.models import Subcategory, Value, Variable
from gobernar360.platform.models import Municipality
from tests.factories import admin_session, make_membership, make_municipality, make_user

BASE = "/api/dashboards/environment"


def environment_member(
    level: str | None = "editor",
    email: str = "ana@noetinger.test",
    municipality: Municipality | None = None,
    municipality_name: str = "Noetinger",
) -> Municipality:
    """Create a user with that level on the environment dashboard; return their municipality."""
    municipality = municipality or make_municipality(municipality_name)
    grants = {"environment": level} if level else {}
    make_membership(make_user(email), municipality, grants=grants, enable=["environment"])
    return municipality


def _add(entity):
    with admin_session() as session, session.begin():
        session.add(entity)
    return entity


def make_subcategory(municipality, category="energy", name="Consumo eléctrico") -> Subcategory:
    return _add(Subcategory(municipality_id=municipality.id, category=category, name=name))


def make_variable(
    municipality, subcategory=None, name="Consumo del palacio municipal", **fields
) -> Variable:
    subcategory = subcategory or make_subcategory(municipality)
    values = {
        "unit": "kWh",
        "frequency": "monthly",
        "direction": "higher_is_better",
        "source": "municipal",
        "annual_aggregation": "sum",
    } | fields
    if values.get("target") is not None:
        values["target"] = Decimal(str(values["target"]))
    return _add(
        Variable(
            municipality_id=municipality.id, subcategory_id=subcategory.id, name=name, **values
        )
    )


def make_value(municipality, variable, year, period, value) -> Value:
    return _add(
        Value(
            municipality_id=municipality.id,
            variable_id=variable.id,
            year=year,
            period=period,
            value=Decimal(str(value)),
        )
    )
