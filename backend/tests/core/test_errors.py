"""Every API error has a status, a stable code the frontend translates, and an English
message for whoever reads the raw response."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from gobernar360.core import errors

ERRORS = [
    (errors.not_authenticated, (), 401, "not_authenticated", "Authentication is required."),
    (errors.forbidden, (), 403, "forbidden", "You do not have access to this resource."),
    (errors.forbidden, ("Admins only.",), 403, "forbidden", "Admins only."),
    (errors.not_found, (), 404, "not_found", "Resource not found."),
    (errors.not_found, ("No such project.",), 404, "not_found", "No such project."),
    (errors.conflict, ("Name taken.",), 409, "conflict", "Name taken."),
    (
        errors.already_registered,
        (),
        409,
        "already_registered",
        "This person is already registered here.",
    ),
    (errors.dni_exists, (), 409, "dni_exists", "Another person already has this document number."),
    (
        errors.household_has_head,
        (),
        409,
        "household_has_head",
        "This household already has a head.",
    ),
    (
        errors.in_another_household,
        (),
        409,
        "in_another_household",
        "This person belongs to another household.",
    ),
    (errors.in_use, (), 409, "in_use", "The resource is referenced by other records."),
    (errors.in_use, ("Still used.",), 409, "in_use", "Still used."),
    (errors.invalid_reference, ("Bad axis.",), 422, "invalid_reference", "Bad axis."),
    (errors.validation_error, ("Bad value.",), 422, "validation_error", "Bad value."),
    (
        errors.future_month,
        (),
        422,
        "future_month",
        "A month that has not started cannot be given a status.",
    ),
    (
        errors.invalid_token,
        (),
        410,
        "invalid_token",
        "The link is not valid: it expired or was already used.",
    ),
    (errors.too_many_requests, (), 429, "too_many_requests", "Too many requests. Try again later."),
]


@pytest.mark.parametrize(("factory", "arguments", "status", "code", "message"), ERRORS)
def test_each_error_has_its_status_code_and_message(factory, arguments, status, code, message):
    # Built inside the test, not in the parameters: mutation testing must see it run.
    error = factory(*arguments)

    assert (error.status_code, error.code, error.message, error.details) == (
        status,
        code,
        message,
        None,
    )
    assert str(error) == message


class _Body(BaseModel):
    name: str = Field(max_length=3)
    count: int


def _client() -> TestClient:
    app = FastAPI()
    errors.install_error_handlers(app)

    @app.get("/plain")
    def plain():
        raise errors.conflict("Name taken.")

    @app.get("/detailed")
    def detailed():
        raise errors.ApiError(422, "validation_error", "Rows failed.", [{"line": 2}])

    @app.post("/validated")
    def validated(body: _Body):
        return body

    return TestClient(app)


def test_an_api_error_becomes_the_error_envelope():
    response = _client().get("/plain")

    assert response.status_code == 409
    assert response.json() == {"error": {"code": "conflict", "message": "Name taken."}}


def test_the_details_of_an_api_error_are_sent_when_it_has_them():
    response = _client().get("/detailed")

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "Rows failed.",
            "details": [{"line": 2}],
        }
    }


def test_an_invalid_request_lists_each_field_that_failed():
    response = _client().post("/validated", json={"name": "Long name"})

    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "validation_error"
    assert body["message"] == "The request is not valid."
    assert [detail["field"] for detail in body["details"]] == ["name", "count"]
    assert body["details"][0]["message"] == "String should have at most 3 characters"
    assert body["details"][1]["message"] == "Field required"


def test_an_invalid_nested_field_is_named_by_its_path():
    app = FastAPI()
    errors.install_error_handlers(app)

    class Outer(BaseModel):
        inner: _Body

    @app.post("/nested")
    def nested(body: Outer):
        return body

    response = TestClient(app).post("/nested", json={"inner": {"name": "ok", "count": "x"}})

    assert response.json()["error"]["details"] == [
        {
            "field": "inner.count",
            "message": "Input should be a valid integer, unable to parse string as an integer",
        }
    ]
