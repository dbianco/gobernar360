from fastapi.testclient import TestClient

from gobernar360.main import create_app


def test_health_endpoint_reports_ok():
    response = TestClient(create_app()).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
