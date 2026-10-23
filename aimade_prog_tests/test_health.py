from fastapi.testclient import TestClient

from app.main import app


def test_health():
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_empty_state():
    with TestClient(app) as client:
        response = client.get("/api/state")
        assert response.status_code == 200
        payload = response.json()
        assert payload["schema_version"] == 1
        assert payload["uploads"] == {}
        assert payload["tasks"] == []
