from fastapi.testclient import TestClient

from app.api.routes import catalog
from app.main import app
from app.services.metadata_generator import MetadataPackage

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


def test_generate_catalog_metadata_rejects_unconfigured_llm() -> None:
    response = client.post(
        "/api/v1/catalog/metadata/generate",
        json={
            "source_title": "Night Rain",
            "mode": "mixed_ambient",
            "duration_seconds": 600,
            "use_llm_metadata": True,
        },
    )

    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_generate_catalog_metadata_routes_to_llm_when_enabled(monkeypatch) -> None:
    package = MetadataPackage(
        title="LLM Title",
        subtitle="LLM Subtitle",
        description="LLM description mentioning medical treatment boundaries.",
        keywords=["llm", "test"],
        category="Sleep",
        language="en",
        compliance_note="Use as ambient or relaxation content.",
    )

    def _fake_generate(**_kwargs):
        return package, 0.002

    monkeypatch.setattr(catalog, "generate_llm_metadata_package", _fake_generate)

    response = client.post(
        "/api/v1/catalog/metadata/generate",
        json={
            "source_title": "Night Rain",
            "mode": "mixed_ambient",
            "duration_seconds": 600,
            "use_llm_metadata": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["title"] == "LLM Title"
