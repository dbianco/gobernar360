"""Builders for projects-dashboard test data, written through the owner connection."""

from gobernar360.dashboards.projects.models import Axis, Department, Objective, Project, Term
from gobernar360.platform.models import Municipality
from tests.factories import admin_session, make_membership, make_municipality, make_user


def projects_member(
    level: str | None = "editor",
    email: str = "ana@noetinger.test",
    municipality: Municipality | None = None,
    municipality_name: str = "Noetinger",
) -> Municipality:
    """Create a user with the given level on the projects dashboard; return their municipality."""
    municipality = municipality or make_municipality(municipality_name)
    grants = {"projects": level} if level else {}
    make_membership(make_user(email), municipality, grants=grants, enable=["projects"])
    return municipality


def _add(entity):
    with admin_session() as session, session.begin():
        session.add(entity)
    return entity


def make_term(municipality, name="Gestión 2023-2027", start_year=2023, end_year=2027) -> Term:
    return _add(
        Term(municipality_id=municipality.id, name=name, start_year=start_year, end_year=end_year)
    )


def make_axis(municipality, term, name="Ciudad inclusiva") -> Axis:
    return _add(Axis(municipality_id=municipality.id, term_id=term.id, name=name))


def make_objective(municipality, axis, name="Reducir el déficit habitacional") -> Objective:
    return _add(Objective(municipality_id=municipality.id, axis_id=axis.id, name=name))


def make_department(municipality, name="Obras Públicas") -> Department:
    return _add(Department(municipality_id=municipality.id, name=name))


def make_project(municipality, term, axis, department, name="Pavimentación", **fields) -> Project:
    values = {"priority": "A", "year": term.start_year, "status": "not_started"} | fields
    return _add(
        Project(
            municipality_id=municipality.id,
            term_id=term.id,
            axis_id=axis.id,
            department_id=department.id,
            name=name,
            **values,
        )
    )
