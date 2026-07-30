from fastapi.testclient import TestClient

from app.api.routes import samples
from app.audio.sample_library import NaturalSoundSample
from app.main import app
from app.schemas.sample import FreesoundSearchResultItem

client = TestClient(app)


def test_search_freesound_returns_results(monkeypatch) -> None:
    monkeypatch.setattr(
        samples,
        "search_cc0_sounds",
        lambda query, *, db, page_size=15: [
            FreesoundSearchResultItem(
                freesound_id=1,
                name="Rain",
                license="Creative Commons 0",
                preview_url="https://freesound.org/preview/1.ogg",
                username="fielder",
                page_url="https://freesound.org/s/1/",
            )
        ],
    )

    response = client.get("/api/v1/audio/samples/freesound/search", params={"query": "rain"})

    assert response.status_code == 200
    body = response.json()
    assert body[0]["freesound_id"] == 1


def test_search_freesound_returns_503_when_unconfigured(monkeypatch) -> None:
    def _raise(*_args, **_kwargs):
        raise ValueError("Freesound import is not configured: set a key")

    monkeypatch.setattr(samples, "search_cc0_sounds", _raise)

    response = client.get("/api/v1/audio/samples/freesound/search", params={"query": "rain"})

    assert response.status_code == 503


def test_import_from_freesound_returns_the_registered_sample(monkeypatch) -> None:
    monkeypatch.setattr(
        samples,
        "import_sample_from_freesound",
        lambda freesound_id, *, sample_id, label, category, db: NaturalSoundSample(
            id=sample_id,
            label=label,
            category=category,
            filename=f"{sample_id}.wav",
            license="Creative Commons 0 (CC0) via Freesound",
            source_url=f"https://freesound.org/s/{freesound_id}/",
            attribution=None,
            source_type="freesound",
        ),
    )

    response = client.post(
        "/api/v1/audio/samples/import-from-freesound",
        json={
            "freesound_id": 42,
            "sample_id": "ocean-waves-fs-01",
            "label": "Ocean Waves",
            "category": "ocean",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source_type"] == "freesound"
    assert body["available"] is True


def test_import_from_freesound_returns_409_on_duplicate_id(monkeypatch) -> None:
    def _raise(*_args, **_kwargs):
        raise ValueError("Sample id already exists: ocean-waves-fs-01")

    monkeypatch.setattr(samples, "import_sample_from_freesound", _raise)

    response = client.post(
        "/api/v1/audio/samples/import-from-freesound",
        json={
            "freesound_id": 42,
            "sample_id": "ocean-waves-fs-01",
            "label": "Ocean Waves",
            "category": "ocean",
        },
    )

    assert response.status_code == 409


def test_import_from_freesound_returns_400_on_non_cc0_license(monkeypatch) -> None:
    def _raise(*_args, **_kwargs):
        raise ValueError("Sound 42 is licensed 'Attribution', not 'Creative Commons 0'")

    monkeypatch.setattr(samples, "import_sample_from_freesound", _raise)

    response = client.post(
        "/api/v1/audio/samples/import-from-freesound",
        json={
            "freesound_id": 42,
            "sample_id": "some-sound",
            "label": "Some Sound",
            "category": "misc",
        },
    )

    assert response.status_code == 400
