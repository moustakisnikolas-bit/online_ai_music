import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies.database import get_db
from app.db.base import Base
from app.main import app
from app.models.app_secret import AppSecret
from app.repositories.app_secrets import MANAGED_SECRET_KEYS
from app.services import token_encryption

client = TestClient(app)


@pytest.fixture(autouse=True)
def _isolated_secrets_db(monkeypatch, tmp_path):
    # This module exercises the real settings API end-to-end (PUT/GET/
    # DELETE secrets), so it needs a real Session -- but MUST NOT be the
    # shared production database the rest of the app uses. The previous
    # version of this fixture called delete_secret() for every managed
    # key against the real SessionLocal-backed database as "cleanup,"
    # which silently wiped every real API key (YouTube, Freesound,
    # Replicate, Internet Archive...) a human had saved through the live
    # app, every single time the test suite ran -- a real incident, not a
    # hypothetical. An isolated in-memory database, injected via FastAPI's
    # own dependency-override mechanism, gives each test a guaranteed
    # clean slate without touching anything real.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[AppSecret.__table__])
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db

    monkeypatch.setattr(token_encryption, "_LOCAL_KEY_FILE", tmp_path / ".local_secret_key")

    class _EmptyEncryptionSettings:
        token_encryption_key = ""

    monkeypatch.setattr(token_encryption, "get_settings", lambda: _EmptyEncryptionSettings())

    yield

    app.dependency_overrides.pop(get_db, None)


def test_list_secret_statuses_returns_every_managed_key() -> None:
    response = client.get("/api/v1/settings/secrets")

    assert response.status_code == 200
    keys = {entry["key"] for entry in response.json()["secrets"]}
    assert keys == set(MANAGED_SECRET_KEYS)


def test_save_secret_marks_it_configured_from_database() -> None:
    response = client.put(
        "/api/v1/settings/secrets/replicate_api_token",
        json={"value": "my-real-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {"key": "replicate_api_token", "configured": True, "source": "database"}


def test_save_secret_rejects_unknown_key() -> None:
    response = client.put(
        "/api/v1/settings/secrets/not_a_real_key",
        json={"value": "irrelevant"},
    )

    assert response.status_code == 404


def test_delete_secret_falls_back_to_unconfigured() -> None:
    client.put(
        "/api/v1/settings/secrets/openrouter_api_key",
        json={"value": "temp-key"},
    )

    response = client.delete("/api/v1/settings/secrets/openrouter_api_key")

    assert response.status_code == 200
    assert response.json() == {
        "key": "openrouter_api_key",
        "configured": False,
        "source": "unconfigured",
    }


def test_delete_secret_rejects_unknown_key() -> None:
    response = client.delete("/api/v1/settings/secrets/not_a_real_key")

    assert response.status_code == 404
