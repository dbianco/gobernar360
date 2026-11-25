import pytest
from fastapi.testclient import TestClient

from gobernar360.main import create_app


@pytest.fixture
def app():
    """Built in each test, so mutmut knows that these are the tests of `create_app`."""
    return create_app()


@pytest.fixture
def client(app):
    return TestClient(app, headers={"X-Requested-With": "gobernar360"})


def test_health_endpoint_reports_ok(app):
    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_the_api_documents_itself_under_api(client):
    schema = client.get("/api/openapi.json").json()

    assert schema["info"]["title"] == "gobernar360"
    assert client.get("/api/docs").status_code == 200
    # Each dashboard's routes are grouped under its key.
    tags = {
        tag
        for path in schema["paths"].values()
        for op in path.values()
        for tag in op.get("tags", [])
    }
    assert {"projects", "environment", "economic", "social", "procedures"} <= tags
    assert schema["paths"]["/api/dashboards/projects/summary"]["get"]["tags"] == ["projects"]


def test_the_web_app_may_call_the_api_with_its_cookies_from_its_own_origin(client):
    preflight = client.options(
        "/api/projects",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "x-requested-with, content-type",
        },
    )

    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert preflight.headers["access-control-allow-credentials"] == "true"
    assert "PATCH" in preflight.headers["access-control-allow-methods"]
    assert preflight.headers["access-control-allow-headers"] == "x-requested-with, content-type"


def test_another_origin_is_not_allowed(client):
    preflight = client.options(
        "/api/projects",
        headers={"Origin": "https://evil.test", "Access-Control-Request-Method": "POST"},
    )

    assert "access-control-allow-origin" not in preflight.headers


def test_unsafe_requests_need_the_csrf_header(app):
    plain = TestClient(app)

    response = plain.post("/api/auth/logout")

    assert response.status_code == 403
    assert response.json()["error"] == {
        "code": "csrf_header_missing",
        "message": "The X-Requested-With header is required.",
    }
    assert plain.get("/api/health").status_code == 200
