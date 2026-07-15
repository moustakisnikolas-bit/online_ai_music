from pathlib import Path

import httpx
import pytest

from app.services import instrumental_generator


class _FakeSettings:
    replicate_api_token = "test-token"
    stable_audio_model = "stackadoc/stable-audio-open-1.0"


class _EmptySettings:
    replicate_api_token = ""
    stable_audio_model = "stackadoc/stable-audio-open-1.0"


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

    def post(self, *_args, **_kwargs) -> _FakeResponse:
        return next(self._responses)

    def get(self, *_args, **_kwargs) -> _FakeResponse:
        return next(self._responses)


def test_generate_instrumental_clip_requires_configuration(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(instrumental_generator, "get_settings", lambda: _EmptySettings())

    with pytest.raises(ValueError, match="not configured"):
        instrumental_generator.generate_instrumental_clip(
            "warm piano pad",
            duration_seconds=20,
            output_path=tmp_path / "clip.wav",
        )


def test_generate_instrumental_clip_succeeds_without_polling(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(instrumental_generator, "get_settings", lambda: _FakeSettings())

    responses = [
        _FakeResponse(
            json_data={
                "status": "succeeded",
                "output": ["https://replicate.example/out.wav"],
                "urls": {"get": "https://api.replicate.com/v1/predictions/abc"},
            }
        ),
        _FakeResponse(content=b"fake-wav-bytes"),
    ]
    monkeypatch.setattr(httpx, "Client", lambda **_kwargs: _FakeClient(responses))

    output_path = tmp_path / "clip.wav"
    result = instrumental_generator.generate_instrumental_clip(
        "warm piano pad",
        duration_seconds=20,
        output_path=output_path,
        seed=42,
    )

    assert result == output_path
    assert output_path.read_bytes() == b"fake-wav-bytes"


def test_generate_instrumental_clip_polls_until_succeeded(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(instrumental_generator, "get_settings", lambda: _FakeSettings())
    monkeypatch.setattr(instrumental_generator.time, "sleep", lambda _seconds: None)

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
                "output": ["https://replicate.example/out.wav"],
            }
        ),
        _FakeResponse(content=b"fake-wav-bytes"),
    ]
    monkeypatch.setattr(httpx, "Client", lambda **_kwargs: _FakeClient(responses))

    output_path = tmp_path / "clip.wav"
    instrumental_generator.generate_instrumental_clip(
        "sustained strings",
        duration_seconds=15,
        output_path=output_path,
    )

    assert output_path.read_bytes() == b"fake-wav-bytes"


def test_generate_instrumental_clip_raises_on_failed_prediction(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(instrumental_generator, "get_settings", lambda: _FakeSettings())

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
        instrumental_generator.generate_instrumental_clip(
            "warm piano pad",
            duration_seconds=20,
            output_path=tmp_path / "clip.wav",
        )


def test_generate_instrumental_clip_times_out(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(instrumental_generator, "get_settings", lambda: _FakeSettings())
    monkeypatch.setattr(instrumental_generator, "_POLL_TIMEOUT_SECONDS", 10)
    monkeypatch.setattr(instrumental_generator.time, "sleep", lambda _seconds: None)

    # A fake clock that jumps far ahead on every call, so the deadline check
    # deterministically trips on the first poll iteration instead of relying
    # on real wall-clock timing at a near-zero threshold (flaky/non-portable).
    clock_state = {"value": 0.0}

    def fake_monotonic() -> float:
        clock_state["value"] += 100.0
        return clock_state["value"]

    monkeypatch.setattr(instrumental_generator.time, "monotonic", fake_monotonic)

    responses = [
        _FakeResponse(
            json_data={
                "status": "processing",
                "output": None,
                "urls": {"get": "https://api.replicate.com/v1/predictions/abc"},
            }
        ),
    ]
    monkeypatch.setattr(httpx, "Client", lambda **_kwargs: _FakeClient(responses))

    with pytest.raises(TimeoutError):
        instrumental_generator.generate_instrumental_clip(
            "warm piano pad",
            duration_seconds=20,
            output_path=tmp_path / "clip.wav",
        )
