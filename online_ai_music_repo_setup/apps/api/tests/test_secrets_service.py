import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.app_secret import AppSecret
from app.repositories.app_secrets import set_secret
from app.services import secrets, token_encryption


class _FakeSettings:
    youtube_client_id = ""
    youtube_client_secret = ""
    replicate_api_token = ""
    openrouter_api_key = ""
    freesound_api_key = ""
    internet_archive_access_key = ""
    internet_archive_secret_key = ""


class _EnvConfiguredSettings:
    youtube_client_id = ""
    youtube_client_secret = ""
    replicate_api_token = "env-replicate-token"
    openrouter_api_key = ""
    freesound_api_key = ""
    internet_archive_access_key = ""
    internet_archive_secret_key = ""


@pytest.fixture
def db(monkeypatch, tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[AppSecret.__table__])

    monkeypatch.setattr(token_encryption, "_LOCAL_KEY_FILE", tmp_path / ".local_secret_key")

    class _EmptyEncryptionSettings:
        token_encryption_key = ""

    monkeypatch.setattr(token_encryption, "get_settings", lambda: _EmptyEncryptionSettings())

    with Session(engine) as session:
        yield session


def test_resolve_secret_uses_env_when_no_override(db, monkeypatch) -> None:
    monkeypatch.setattr(secrets, "get_settings", lambda: _EnvConfiguredSettings())

    assert secrets.resolve_secret(db, "replicate_api_token") == "env-replicate-token"


def test_resolve_secret_prefers_database_override(db, monkeypatch) -> None:
    monkeypatch.setattr(secrets, "get_settings", lambda: _EnvConfiguredSettings())
    set_secret(db, key="replicate_api_token", value="database-saved-token")

    assert secrets.resolve_secret(db, "replicate_api_token") == "database-saved-token"


def test_resolve_secret_returns_empty_when_neither_set(db, monkeypatch) -> None:
    monkeypatch.setattr(secrets, "get_settings", lambda: _FakeSettings())

    assert secrets.resolve_secret(db, "openrouter_api_key") == ""


def test_secret_status_unconfigured(db, monkeypatch) -> None:
    monkeypatch.setattr(secrets, "get_settings", lambda: _FakeSettings())

    status = secrets.secret_status(db, "openrouter_api_key")

    assert status == {"key": "openrouter_api_key", "configured": False, "source": "unconfigured"}


def test_secret_status_environment(db, monkeypatch) -> None:
    monkeypatch.setattr(secrets, "get_settings", lambda: _EnvConfiguredSettings())

    status = secrets.secret_status(db, "replicate_api_token")

    assert status == {"key": "replicate_api_token", "configured": True, "source": "environment"}


def test_secret_status_database_wins_over_environment(db, monkeypatch) -> None:
    monkeypatch.setattr(secrets, "get_settings", lambda: _EnvConfiguredSettings())
    set_secret(db, key="replicate_api_token", value="database-saved-token")

    status = secrets.secret_status(db, "replicate_api_token")

    assert status == {"key": "replicate_api_token", "configured": True, "source": "database"}


def test_all_secret_statuses_covers_every_managed_key(db, monkeypatch) -> None:
    monkeypatch.setattr(secrets, "get_settings", lambda: _FakeSettings())

    statuses = secrets.all_secret_statuses(db)

    assert {entry["key"] for entry in statuses} == {
        "youtube_client_id",
        "youtube_client_secret",
        "replicate_api_token",
        "openrouter_api_key",
        "freesound_api_key",
        "internet_archive_access_key",
        "internet_archive_secret_key",
    }
