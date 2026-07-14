from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_generate_catalog_metadata() -> None:
    response = client.post(
        "/api/v1/catalog/metadata/generate",
        json={
            "source_title": "Night Rain",
            "mode": "mixed_ambient",
            "duration_seconds": 600,
            "context": "sleep",
            "language": "en",
            "frequency_hz": 432,
            "texture_mode": "rain",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["category"] == "Sleep"
    assert "Night Rain" in payload["title"]
    assert "medical treatment" in payload["description"]
