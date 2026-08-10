from fastapi.testclient import TestClient

from app.main import create_app


def test_healthz_returns_app_identity() -> None:
    client = TestClient(create_app())

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["app_name"] == "Cloud AI Software Ecosystem Updates"
