from fastapi.testclient import TestClient

from app.api.routes import publishing_internet_archive
from app.main import app

client = TestClient(app)


def test_status_reports_unconfigured_by_default(monkeypatch) -> None:
    def _raise(_db):
        raise ValueError("Internet Archive publishing is not configured")

    monkeypatch.setattr(publishing_internet_archive, "ensure_configured", _raise)

    response = client.get("/api/v1/publishing/internet-archive/status")

    assert response.status_code == 200
    assert response.json() == {"configured": False}


def test_status_reports_configured(monkeypatch) -> None:
    monkeypatch.setattr(
        publishing_internet_archive, "ensure_configured", lambda _db: ("key", "secret")
    )

    response = client.get("/api/v1/publishing/internet-archive/status")

    assert response.status_code == 200
    assert response.json() == {"configured": True}


def test_upload_returns_404_for_unknown_job() -> None:
    response = client.post(
        "/api/v1/publishing/internet-archive/uploads",
        json={
            "audio_job_id": "11111111-1111-1111-1111-111111111111",
            "audio_filename": "does-not-matter.wav",
            "title": "Night Rain",
        },
    )

    assert response.status_code == 409
