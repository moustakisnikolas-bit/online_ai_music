import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.app_secret import AppSecret
from app.repositories.app_secrets import (
    delete_secret,
    get_secret_value,
    is_secret_overridden,
    set_secret,
)
from app.services import token_encryption


@pytest.fixture
def db(monkeypatch, tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[AppSecret.__table__])

    # Real encrypt_token/decrypt_token round-trip, isolated from the real
    # project directory's auto-generated key file.
    monkeypatch.setattr(token_encryption, "_LOCAL_KEY_FILE", tmp_path / ".local_secret_key")

    class _EmptySettings:
        token_encryption_key = ""

    monkeypatch.setattr(token_encryption, "get_settings", lambda: _EmptySettings())

    with Session(engine) as session:
        yield session


def test_set_then_get_round_trips_through_real_encryption(db) -> None:
    set_secret(db, key="replicate_api_token", value="r8_test_token_123")

    assert get_secret_value(db, "replicate_api_token") == "r8_test_token_123"


def test_set_stores_an_encrypted_value_not_plaintext(db) -> None:
    record = set_secret(db, key="openrouter_api_key", value="sk-or-plaintext-value")

    assert record.value_encrypted != "sk-or-plaintext-value"


def test_set_upserts_on_second_call(db) -> None:
    first = set_secret(db, key="youtube_client_id", value="first-value")
    second = set_secret(db, key="youtube_client_id", value="second-value")

    assert first.id == second.id
    assert get_secret_value(db, "youtube_client_id") == "second-value"


def test_get_secret_value_returns_none_when_unset(db) -> None:
    assert get_secret_value(db, "replicate_api_token") is None


def test_is_secret_overridden_reflects_presence(db) -> None:
    assert is_secret_overridden(db, "replicate_api_token") is False

    set_secret(db, key="replicate_api_token", value="x")

    assert is_secret_overridden(db, "replicate_api_token") is True


def test_delete_secret_removes_the_override(db) -> None:
    set_secret(db, key="replicate_api_token", value="x")

    assert delete_secret(db, key="replicate_api_token") is True
    assert get_secret_value(db, "replicate_api_token") is None
    assert is_secret_overridden(db, "replicate_api_token") is False


def test_delete_secret_returns_false_when_nothing_to_delete(db) -> None:
    assert delete_secret(db, key="replicate_api_token") is False


def test_unknown_key_is_rejected(db) -> None:
    with pytest.raises(ValueError, match="Unknown secret key"):
        set_secret(db, key="not_a_real_key", value="x")

    with pytest.raises(ValueError, match="Unknown secret key"):
        get_secret_value(db, "not_a_real_key")
