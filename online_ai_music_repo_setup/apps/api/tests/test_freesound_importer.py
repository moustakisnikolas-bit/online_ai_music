import io
from pathlib import Path

import httpx
import numpy as np
import pytest
import soundfile as sf
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.audio.sample_library import get_sample, resolve_sample_audio_path
from app.db.base import Base
from app.models.app_secret import AppSecret
from app.services import freesound_importer
from app.services import secrets as secrets_service
from app.services import token_encryption


class _FakeSettings:
    freesound_api_key = "test-freesound-key"


class _EmptySettings:
    freesound_api_key = ""


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


def _patch_settings(monkeypatch, settings_obj) -> None:
    monkeypatch.setattr(secrets_service, "get_settings", lambda: settings_obj)


class _FakeResponse:
    def __init__(self, json_data: dict | None = None, content: bytes = b"") -> None:
        self._json_data = json_data
        self.content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._json_data


class _FakeClient:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self._responses = iter(responses)

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, *args) -> bool:
        return False

    def get(self, *_args, **_kwargs) -> _FakeResponse:
        return next(self._responses)


def _fake_wav_bytes(seconds: float = 0.5, sample_rate: int = 44100) -> bytes:
    # A real, decodable WAV -- soundfile sniffs the format from the header,
    # not the URL's ".ogg" extension, so this stands in fine for testing
    # the decode round trip without depending on the local libsndfile
    # build's OGG/Vorbis support.
    t = np.arange(int(seconds * sample_rate)) / sample_rate
    samples = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    buffer = io.BytesIO()
    sf.write(buffer, samples, sample_rate, format="WAV", subtype="PCM_16")
    return buffer.getvalue()


def test_search_cc0_sounds_requires_configuration(monkeypatch, db) -> None:
    _patch_settings(monkeypatch, _EmptySettings())

    with pytest.raises(ValueError, match="not configured"):
        freesound_importer.search_cc0_sounds("rain", db=db)


def test_search_cc0_sounds_filters_and_maps_results(monkeypatch, db) -> None:
    _patch_settings(monkeypatch, _FakeSettings())

    responses = [
        _FakeResponse(
            json_data={
                "results": [
                    {
                        "id": 123,
                        "name": "Rain on window",
                        "license": "Creative Commons 0",
                        "previews": {"preview-hq-ogg": "https://freesound.org/preview/123.ogg"},
                        "username": "fielder",
                        "url": "https://freesound.org/s/123/",
                    }
                ]
            }
        )
    ]
    monkeypatch.setattr(httpx, "Client", lambda **_kwargs: _FakeClient(responses))

    results = freesound_importer.search_cc0_sounds("rain", db=db)

    assert len(results) == 1
    assert results[0].freesound_id == 123
    assert results[0].license == "Creative Commons 0"
    assert results[0].preview_url == "https://freesound.org/preview/123.ogg"


def test_import_sample_from_freesound_rejects_non_cc0_license(monkeypatch, db) -> None:
    _patch_settings(monkeypatch, _FakeSettings())

    responses = [
        _FakeResponse(
            json_data={
                "id": 999,
                "name": "Some Sound",
                "license": "Attribution",
                "previews": {"preview-hq-ogg": "https://freesound.org/preview/999.ogg"},
                "username": "someone",
                "url": "https://freesound.org/s/999/",
            }
        )
    ]
    monkeypatch.setattr(httpx, "Client", lambda **_kwargs: _FakeClient(responses))

    with pytest.raises(ValueError, match="not a recognized CC0 value"):
        freesound_importer.import_sample_from_freesound(
            999,
            sample_id="some-sound",
            label="Some Sound",
            category="misc",
            db=db,
        )


def test_import_sample_from_freesound_accepts_the_cc0_url_form_license(
    monkeypatch, tmp_path: Path, db
) -> None:
    # Regression test: Freesound's docs describe the license field as the
    # plain string "Creative Commons 0", but a real batch import found
    # GET /sounds/<id>/ actually returns this URL form instead -- both
    # must be accepted as valid CC0.
    _patch_settings(monkeypatch, _FakeSettings())
    manifest_path = tmp_path / "manifest.json"

    responses = [
        _FakeResponse(
            json_data={
                "id": 42,
                "name": "Ocean Waves",
                "license": "http://creativecommons.org/publicdomain/zero/1.0/",
                "previews": {"preview-hq-ogg": "https://freesound.org/preview/42.ogg"},
                "username": "fielder",
                "url": "https://freesound.org/s/42/",
            }
        ),
        _FakeResponse(content=_fake_wav_bytes()),
    ]
    monkeypatch.setattr(httpx, "Client", lambda **_kwargs: _FakeClient(responses))

    sample = freesound_importer.import_sample_from_freesound(
        42,
        sample_id="ocean-waves-fs-01",
        label="Ocean Waves",
        category="ocean",
        db=db,
        library_dir=tmp_path,
        manifest_path=manifest_path,
    )

    assert sample.source_type == "freesound"


def test_import_sample_from_freesound_decodes_and_registers(monkeypatch, tmp_path: Path, db) -> None:
    _patch_settings(monkeypatch, _FakeSettings())
    manifest_path = tmp_path / "manifest.json"

    responses = [
        _FakeResponse(
            json_data={
                "id": 42,
                "name": "Ocean Waves",
                "license": "Creative Commons 0",
                "previews": {"preview-hq-ogg": "https://freesound.org/preview/42.ogg"},
                "username": "fielder",
                "url": "https://freesound.org/s/42/",
            }
        ),
        _FakeResponse(content=_fake_wav_bytes()),
    ]
    monkeypatch.setattr(httpx, "Client", lambda **_kwargs: _FakeClient(responses))

    sample = freesound_importer.import_sample_from_freesound(
        42,
        sample_id="ocean-waves-fs-01",
        label="Ocean Waves",
        category="ocean",
        db=db,
        library_dir=tmp_path,
        manifest_path=manifest_path,
    )

    assert sample.source_type == "freesound"
    assert sample.source_url == "https://freesound.org/s/42/"
    assert (tmp_path / "ocean-waves-fs-01.wav").exists()

    registered = get_sample("ocean-waves-fs-01", manifest_path=manifest_path)
    resolved_path = resolve_sample_audio_path(registered, library_dir=tmp_path)
    assert resolved_path.exists()


def test_import_sample_from_freesound_trims_long_recordings_by_default(
    monkeypatch, tmp_path: Path, db
) -> None:
    # Regression test for a real batch import that pulled down several
    # 15-30+ minute field recordings, decoded to raw PCM WAV -- tens to
    # hundreds of MB for a sample library entry that only ever gets
    # looped anyway (load_sample_layer tiles it to fill the requested
    # duration, so there's no benefit to keeping the full length).
    _patch_settings(monkeypatch, _FakeSettings())
    manifest_path = tmp_path / "manifest.json"
    sample_rate = 44100

    responses = [
        _FakeResponse(
            json_data={
                "id": 99,
                "name": "Long Field Recording",
                "license": "Creative Commons 0",
                "previews": {"preview-hq-ogg": "https://freesound.org/preview/99.ogg"},
                "username": "fielder",
                "url": "https://freesound.org/s/99/",
            }
        ),
        _FakeResponse(content=_fake_wav_bytes(seconds=300, sample_rate=sample_rate)),
    ]
    monkeypatch.setattr(httpx, "Client", lambda **_kwargs: _FakeClient(responses))

    freesound_importer.import_sample_from_freesound(
        99,
        sample_id="long-recording",
        label="Long Field Recording",
        category="misc",
        db=db,
        library_dir=tmp_path,
        manifest_path=manifest_path,
        max_duration_seconds=10,
    )

    with sf.SoundFile(str(tmp_path / "long-recording.wav")) as f:
        assert f.frames == 10 * sample_rate
