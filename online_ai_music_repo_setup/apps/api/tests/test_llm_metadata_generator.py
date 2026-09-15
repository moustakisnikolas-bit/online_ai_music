import json

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.app_secret import AppSecret
from app.services import llm_metadata_generator
from app.services import secrets as secrets_service
from app.services import token_encryption


class _FakeSettings:
    openrouter_api_key = "test-openrouter-key"
    openrouter_text_model = "anthropic/claude-3.5-haiku"


class _EmptySettings:
    openrouter_api_key = ""
    openrouter_text_model = "anthropic/claude-3.5-haiku"


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
    # require_openrouter_key() (provider_config.py) calls resolve_secret()
    # (secrets.py), which reads its own get_settings import -- separate
    # from this module's, which still needs patching for non-secret
    # settings like the text model name.
    monkeypatch.setattr(llm_metadata_generator, "get_settings", lambda: settings_obj)
    monkeypatch.setattr(secrets_service, "get_settings", lambda: settings_obj)


class _FakeResponse:
    def __init__(self, json_data: dict) -> None:
        self._json_data = json_data

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._json_data


class _FakeClient:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, *args) -> bool:
        return False

    def post(self, *_args, **_kwargs) -> _FakeResponse:
        return self._response


def _chat_response(content: dict, cost: float | None = 0.001) -> _FakeResponse:
    usage = {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
    if cost is not None:
        usage["cost"] = cost

    return _FakeResponse(
        {
            "choices": [{"message": {"content": json.dumps(content)}}],
            "usage": usage,
        }
    )


def test_requires_configuration(monkeypatch, db) -> None:
    _patch_settings(monkeypatch, _EmptySettings())

    with pytest.raises(ValueError, match="not configured"):
        llm_metadata_generator.generate_llm_metadata_package(
            source_title="Night Rain",
            mode="mixed_ambient",
            duration_seconds=600,
            db=db,
        )


def test_generates_package_and_reports_cost(monkeypatch, db) -> None:
    _patch_settings(monkeypatch, _FakeSettings())

    response = _chat_response(
        {
            "title": "Night Rain — Deep Sleep",
            "subtitle": "Mixed Ambient · 10 Minutes",
            "description": "A calming rain soundscape for sleep.",
            "keywords": ["Rain", "Sleep", "Ambient", "Relax", "Night"],
        },
        cost=0.0021,
    )
    monkeypatch.setattr(httpx, "Client", lambda **_kwargs: _FakeClient(response))

    package, cost_usd = llm_metadata_generator.generate_llm_metadata_package(
        source_title="Night Rain",
        mode="mixed_ambient",
        duration_seconds=600,
        db=db,
        context="sleep",
    )

    assert package.title == "Night Rain — Deep Sleep"
    assert package.category == "Sleep"
    assert "rain" in package.keywords
    assert cost_usd == 0.0021
    # Compliance language is never LLM-generated.
    assert "medical treatment" in package.compliance_note


def test_generates_package_with_baby_compliance_note_for_baby_context(monkeypatch, db) -> None:
    _patch_settings(monkeypatch, _FakeSettings())

    response = _chat_response(
        {
            "title": "Womb Whoosh — Baby Sleep",
            "subtitle": "Mixed Ambient · 15 Minutes",
            "description": "A steady womb-like whoosh for infant sleep.",
            "keywords": ["baby", "womb", "sleep", "white noise", "infant"],
        },
        cost=0.0018,
    )
    monkeypatch.setattr(httpx, "Client", lambda **_kwargs: _FakeClient(response))

    package, _cost_usd = llm_metadata_generator.generate_llm_metadata_package(
        source_title="Womb Whoosh",
        mode="mixed_ambient",
        duration_seconds=895,
        db=db,
        context="baby_womb",
    )

    assert "crib" in package.compliance_note
    assert package.category == "Baby Womb Sounds"


def test_missing_cost_returns_none(monkeypatch, db) -> None:
    _patch_settings(monkeypatch, _FakeSettings())

    response = _chat_response(
        {
            "title": "Night Rain",
            "subtitle": "Ambient",
            "description": "Rain sounds.",
            "keywords": ["rain"],
        },
        cost=None,
    )
    monkeypatch.setattr(httpx, "Client", lambda **_kwargs: _FakeClient(response))

    _package, cost_usd = llm_metadata_generator.generate_llm_metadata_package(
        source_title="Night Rain",
        mode="mixed_ambient",
        duration_seconds=600,
        db=db,
    )

    assert cost_usd is None


def test_malformed_response_raises_runtime_error(monkeypatch, db) -> None:
    _patch_settings(monkeypatch, _FakeSettings())

    response = _FakeResponse({"choices": [{"message": {"content": "not json"}}]})
    monkeypatch.setattr(httpx, "Client", lambda **_kwargs: _FakeClient(response))

    with pytest.raises(RuntimeError, match="Unexpected LLM metadata response shape"):
        llm_metadata_generator.generate_llm_metadata_package(
            source_title="Night Rain",
            mode="mixed_ambient",
            duration_seconds=600,
            db=db,
        )


def test_missing_keys_raises_runtime_error(monkeypatch, db) -> None:
    _patch_settings(monkeypatch, _FakeSettings())

    response = _chat_response({"title": "Night Rain"})
    monkeypatch.setattr(httpx, "Client", lambda **_kwargs: _FakeClient(response))

    with pytest.raises(RuntimeError, match="Unexpected LLM metadata response shape"):
        llm_metadata_generator.generate_llm_metadata_package(
            source_title="Night Rain",
            mode="mixed_ambient",
            duration_seconds=600,
            db=db,
        )
