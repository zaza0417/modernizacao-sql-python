from fastapi.testclient import TestClient

from modernizer.api.app import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_modernize_requires_source_code():
    assert client.post("/modernize", json={}).status_code == 422
