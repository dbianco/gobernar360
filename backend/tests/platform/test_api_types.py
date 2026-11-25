"""Request building blocks shared by the dashboards."""

from typing import ClassVar

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from gobernar360.platform.api_types import Name, OrmModel, PatchModel, Year


class Patch(PatchModel):
    nullable: ClassVar[frozenset[str]] = frozenset({"area"})

    name: Name | None = None
    area: str | None = None
    note: str | None = None


def test_absent_fields_are_left_alone_and_only_some_can_be_cleared():
    assert Patch.model_validate({}).model_dump(exclude_unset=True) == {}
    assert Patch.model_validate({"area": None}).model_dump(exclude_unset=True) == {"area": None}


def test_every_field_cleared_that_cannot_be_is_named_in_order():
    with pytest.raises(ValidationError, match="name, note cannot be null"):
        Patch.model_validate({"note": None, "name": None, "area": None})


def test_something_that_is_not_an_object_is_refused_as_such():
    with pytest.raises(ValidationError, match="valid dictionary"):
        Patch.model_validate(["name"])


def test_an_instance_is_taken_as_it_is():
    patch = Patch(name="Obras")

    assert Patch.model_validate(patch) is patch


@pytest.mark.parametrize(("text", "name"), [(" Obras ", "Obras"), ("x" * 200, "x" * 200)])
def test_names_are_trimmed(text, name):
    assert TypeAdapter(Name).validate_python(text) == name


@pytest.mark.parametrize("text", ["", "   ", "x" * 201])
def test_names_are_neither_blank_nor_endless(text):
    with pytest.raises(ValidationError):
        TypeAdapter(Name).validate_python(text)


@pytest.mark.parametrize(("year", "valid"), [(1899, 0), (1900, 1), (2200, 1), (2201, 0)])
def test_years_have_limits(year, valid):
    class Body(BaseModel):
        year: Year

    if valid:
        assert Body(year=year).year == year
    else:
        with pytest.raises(ValidationError):
            Body(year=year)


def test_answers_are_read_from_objects():
    class Row:
        name = "Obras"

    class Out(OrmModel):
        name: str

    assert Out.model_validate(Row()).name == "Obras"
