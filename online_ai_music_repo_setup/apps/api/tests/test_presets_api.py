from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_presets() -> None:
    response = client.get("/api/v1/audio/presets")

    assert response.status_code == 200
    payload = response.json()

    assert len(payload) >= 4
    assert any(item["name"] == "calm-432" for item in payload)


def test_get_unknown_preset_returns_404() -> None:
    response = client.get("/api/v1/audio/presets/does-not-exist")

    assert response.status_code == 404
