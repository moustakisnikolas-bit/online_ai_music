import uuid

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.app_secret import AppSecret
from app.services import internet_archive_publisher
from app.services import secrets as secrets_service
from app.services import token_encryption


class _FakeSettings:
    internet_archive_access_key = "test-access-key"
    internet_archive_secret_key = "test-secret-key"


class _EmptySettings:
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


def test_ensure_configured_requires_both_keys(monkeypatch, db) -> None:
    monkeypatch.setattr(secrets_service, "get_settings", lambda: _EmptySettings())

    with pytest.raises(ValueError, match="not configured"):
        internet_archive_publisher.ensure_configured(db)


def test_ensure_configured_returns_key_pair(monkeypatch, db) -> None:
    monkeypatch.setattr(secrets_service, "get_settings", lambda: _FakeSettings())

    access_key, secret_key = internet_archive_publisher.ensure_configured(db)

    assert access_key == "test-access-key"
    assert secret_key == "test-secret-key"


def test_build_item_identifier_is_url_safe_and_unique_per_job() -> None:
    job_id = uuid.uuid4()

    identifier = internet_archive_publisher.build_item_identifier("Night Rain! 432", job_id)

    assert identifier.startswith("night-rain-432-")
    assert identifier.endswith(str(job_id)[:8])
    assert " " not in identifier
    assert "!" not in identifier


def test_build_item_identifier_falls_back_for_empty_title() -> None:
    job_id = uuid.uuid4()

    identifier = internet_archive_publisher.build_item_identifier("!!!", job_id)

    assert identifier.startswith("aion-track-")


def test_upload_track_raises_for_missing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        internet_archive_publisher.upload_track(
            access_key="k",
            secret_key="s",
            item_identifier="missing-item",
            audio_path=tmp_path / "missing.wav",
            title="Night Rain",
        )


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None


class _FakeClient:
    def __init__(self, calls: list[dict]) -> None:
        self._calls = calls

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, *args) -> bool:
        return False

    def put(self, url, *, headers, content):
        self._calls.append({"url": url, "headers": headers})
        return _FakeResponse()


def test_upload_track_sends_expected_headers_and_returns_item_url(monkeypatch, tmp_path) -> None:
    audio_path = tmp_path / "night-rain.wav"
    audio_path.write_bytes(b"fake wav bytes")

    calls: list[dict] = []
    monkeypatch.setattr(httpx, "Client", lambda **_kwargs: _FakeClient(calls))

    archive_url = internet_archive_publisher.upload_track(
        access_key="my-access-key",
        secret_key="my-secret-key",
        item_identifier="night-rain-abcd1234",
        audio_path=audio_path,
        title="Night Rain",
        description="a calm ambient track",
        creator="AION",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
    )

    assert archive_url == "https://archive.org/details/night-rain-abcd1234"
    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == "https://s3.us.archive.org/night-rain-abcd1234/night-rain.wav"
    assert call["headers"]["Authorization"] == "LOW my-access-key:my-secret-key"
    assert call["headers"]["x-archive-auto-make-bucket"] == "1"
    assert call["headers"]["x-archive-meta-title"] == "Night Rain"
    assert call["headers"]["x-archive-meta-description"] == "a calm ambient track"
    assert call["headers"]["x-archive-meta-creator"] == "AION"
    assert (
        call["headers"]["x-archive-meta-licenseurl"]
        == "https://creativecommons.org/publicdomain/zero/1.0/"
    )
