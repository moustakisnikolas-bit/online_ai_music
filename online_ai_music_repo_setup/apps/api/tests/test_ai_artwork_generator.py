import base64
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.app_secret import AppSecret
from app.services import ai_artwork_generator, replicate_client
from app.services import secrets as secrets_service
from app.services import token_encryption


class _FakeSettings:
    replicate_api_token = "test-replicate-token"
    flux_model = "black-forest-labs/flux-1.1-pro"
    openrouter_api_key = "test-openrouter-key"
    openrouter_image_model = "bytedance-seed/seedream-4.5"


class _EmptySettings:
    replicate_api_token = ""
    flux_model = "black-forest-labs/flux-1.1-pro"
    openrouter_api_key = ""
    openrouter_image_model = "bytedance-seed/seedream-4.5"


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
    # resolve_secret() (secrets.py), used by both provider_config.py's
    # require_openrouter_key() and this module's own replicate check, reads
    # its own get_settings import -- separate from this module's, which
    # still needs patching for non-secret settings like model names.
    monkeypatch.setattr(ai_artwork_generator, "get_settings", lambda: settings_obj)
    monkeypatch.setattr(secrets_service, "get_settings", lambda: settings_obj)


class _FakeResponse:
    def __init__(
        self, json_data: dict | None = None, content: bytes = b"", status_code: int = 200
    ) -> None:
        self._json_data = json_data
        self.content = content
        self.status_code = status_code

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._json_data


class _FakeClient:
    def __init__(self, responses: list[_FakeResponse], calls: list[dict] | None = None) -> None:
        self._responses = iter(responses)
        self._calls = calls

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, *args) -> bool:
        return False

    def post(self, *args, **kwargs) -> _FakeResponse:
        if self._calls is not None:
            self._calls.append({"args": args, "kwargs": kwargs})
        return next(self._responses)

    def get(self, *_args, **_kwargs) -> _FakeResponse:
        return next(self._responses)


def test_aspect_ratio_for_reduces_to_lowest_terms() -> None:
    assert ai_artwork_generator.aspect_ratio_for(3000, 3000) == "1:1"
    assert ai_artwork_generator.aspect_ratio_for(1280, 720) == "16:9"


def test_replicate_provider_requires_configuration(monkeypatch, tmp_path: Path, db) -> None:
    _patch_settings(monkeypatch, _EmptySettings())

    with pytest.raises(ValueError, match="not configured"):
        ai_artwork_generator.generate_ai_artwork(
            "a calm forest",
            output_path=tmp_path / "art.png",
            provider="replicate",
            width=1024,
            height=1024,
            db=db,
        )


def test_openrouter_provider_requires_configuration(monkeypatch, tmp_path: Path, db) -> None:
    _patch_settings(monkeypatch, _EmptySettings())

    with pytest.raises(ValueError, match="not configured"):
        ai_artwork_generator.generate_ai_artwork(
            "a calm forest",
            output_path=tmp_path / "art.png",
            provider="openrouter",
            width=1024,
            height=1024,
            db=db,
        )


def test_replicate_provider_succeeds_without_polling(monkeypatch, tmp_path: Path, db) -> None:
    _patch_settings(monkeypatch, _FakeSettings())

    responses = [
        _FakeResponse(
            json_data={
                "status": "succeeded",
                "output": ["https://replicate.example/out.png"],
                "urls": {"get": "https://api.replicate.com/v1/predictions/abc"},
            }
        ),
        _FakeResponse(content=b"fake-png-bytes"),
    ]
    monkeypatch.setattr(httpx, "Client", lambda **_kwargs: _FakeClient(responses))

    output_path = tmp_path / "art.png"
    result = ai_artwork_generator.generate_ai_artwork(
        "a calm forest",
        output_path=output_path,
        provider="replicate",
        width=3000,
        height=3000,
        seed=7,
        db=db,
    )

    assert result.path == output_path
    assert result.cost_usd is None
    assert output_path.read_bytes() == b"fake-png-bytes"


def test_replicate_provider_requests_png_output_format(monkeypatch, tmp_path: Path, db) -> None:
    # Regression test: flux-schnell's real default output_format is
    # "webp" (verified directly against Replicate's own model schema),
    # but this app always saves artwork under a ".png" filename -- a real
    # generated file was found to actually be WEBP content despite the
    # name. Explicitly requesting "png" keeps the file honest.
    _patch_settings(monkeypatch, _FakeSettings())

    responses = [
        _FakeResponse(
            json_data={
                "status": "succeeded",
                "output": ["https://replicate.example/out.png"],
                "urls": {"get": "https://api.replicate.com/v1/predictions/abc"},
            }
        ),
        _FakeResponse(content=b"fake-png-bytes"),
    ]
    calls: list[dict] = []
    monkeypatch.setattr(httpx, "Client", lambda **_kwargs: _FakeClient(responses, calls))

    ai_artwork_generator.generate_ai_artwork(
        "a calm forest",
        output_path=tmp_path / "art.png",
        provider="replicate",
        width=1024,
        height=1024,
        db=db,
    )

    assert calls[0]["kwargs"]["json"]["input"]["output_format"] == "png"


def test_replicate_provider_polls_until_succeeded(monkeypatch, tmp_path: Path, db) -> None:
    _patch_settings(monkeypatch, _FakeSettings())
    monkeypatch.setattr(replicate_client.time, "sleep", lambda _seconds: None)

    responses = [
        _FakeResponse(
            json_data={
                "status": "starting",
                "output": None,
                "urls": {"get": "https://api.replicate.com/v1/predictions/abc"},
            }
        ),
        _FakeResponse(json_data={"status": "processing", "output": None}),
        _FakeResponse(
            json_data={
                "status": "succeeded",
                "output": ["https://replicate.example/out.png"],
            }
        ),
        _FakeResponse(content=b"fake-png-bytes"),
    ]
    monkeypatch.setattr(httpx, "Client", lambda **_kwargs: _FakeClient(responses))

    output_path = tmp_path / "art.png"
    ai_artwork_generator.generate_ai_artwork(
        "a calm forest",
        output_path=output_path,
        provider="replicate",
        width=1024,
        height=1024,
        db=db,
    )

    assert output_path.read_bytes() == b"fake-png-bytes"


def test_replicate_provider_raises_on_failed_prediction(monkeypatch, tmp_path: Path, db) -> None:
    _patch_settings(monkeypatch, _FakeSettings())

    responses = [
        _FakeResponse(
            json_data={
                "status": "failed",
                "error": "model exploded",
                "urls": {"get": "https://api.replicate.com/v1/predictions/abc"},
            }
        ),
    ]
    monkeypatch.setattr(httpx, "Client", lambda **_kwargs: _FakeClient(responses))

    with pytest.raises(RuntimeError, match="model exploded"):
        ai_artwork_generator.generate_ai_artwork(
            "a calm forest",
            output_path=tmp_path / "art.png",
            provider="replicate",
            width=1024,
            height=1024,
            db=db,
        )


def test_openrouter_provider_decodes_base64_image_and_reports_cost(
    monkeypatch, tmp_path: Path, db
) -> None:
    _patch_settings(monkeypatch, _FakeSettings())

    raw_bytes = b"fake-png-bytes"
    responses = [
        _FakeResponse(
            json_data={
                "data": [
                    {
                        "b64_json": base64.b64encode(raw_bytes).decode("ascii"),
                        "media_type": "image/png",
                    }
                ],
                "usage": {"cost": 0.04},
            }
        ),
    ]
    monkeypatch.setattr(httpx, "Client", lambda **_kwargs: _FakeClient(responses))

    output_path = tmp_path / "art.png"
    result = ai_artwork_generator.generate_ai_artwork(
        "a calm forest",
        output_path=output_path,
        provider="openrouter",
        width=1280,
        height=720,
        seed=3,
        db=db,
    )

    assert result.path == output_path
    assert result.cost_usd == 0.04
    assert output_path.read_bytes() == raw_bytes


def test_openrouter_provider_handles_missing_usage_cost(monkeypatch, tmp_path: Path, db) -> None:
    _patch_settings(monkeypatch, _FakeSettings())

    responses = [
        _FakeResponse(
            json_data={
                "data": [
                    {
                        "b64_json": base64.b64encode(b"fake-png-bytes").decode("ascii"),
                        "media_type": "image/png",
                    }
                ],
            }
        ),
    ]
    monkeypatch.setattr(httpx, "Client", lambda **_kwargs: _FakeClient(responses))

    result = ai_artwork_generator.generate_ai_artwork(
        "a calm forest",
        output_path=tmp_path / "art.png",
        provider="openrouter",
        width=1280,
        height=720,
        db=db,
    )

    assert result.cost_usd is None


def test_openrouter_provider_raises_on_unexpected_response_shape(
    monkeypatch, tmp_path: Path, db
) -> None:
    _patch_settings(monkeypatch, _FakeSettings())

    responses = [_FakeResponse(json_data={"data": []})]
    monkeypatch.setattr(httpx, "Client", lambda **_kwargs: _FakeClient(responses))

    with pytest.raises(RuntimeError, match="Unexpected OpenRouter"):
        ai_artwork_generator.generate_ai_artwork(
            "a calm forest",
            output_path=tmp_path / "art.png",
            provider="openrouter",
            width=1024,
            height=1024,
            db=db,
        )


def test_unknown_provider_raises_value_error(monkeypatch, tmp_path: Path, db) -> None:
    _patch_settings(monkeypatch, _FakeSettings())

    with pytest.raises(ValueError, match="Unknown AI artwork provider"):
        ai_artwork_generator.generate_ai_artwork(
            "a calm forest",
            output_path=tmp_path / "art.png",
            provider="not-a-real-provider",
            width=1024,
            height=1024,
            db=db,
        )
