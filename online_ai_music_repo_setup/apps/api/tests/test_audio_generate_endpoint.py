from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_generate_mp3_without_ffmpeg_returns_clean_400(monkeypatch) -> None:
    # Regression test: encode_audio raises RuntimeError (not OSError or
    # ValueError) when ffmpeg isn't available, but the route only caught
    # (OSError, ValueError) -- so this surfaced as an unhandled 500 with no
    # useful detail instead of a clear 400, found via real browser usage
    # against an environment with no ffmpeg installed.
    monkeypatch.setattr(
        "app.services.audio_encoding.ffmpeg_available",
        lambda: False,
    )

    response = client.post(
        "/api/v1/audio/generate",
        json={
            "title": "MP3 Without FFmpeg",
            "mode": "sine",
            "frequency_hz": 432,
            "duration_seconds": 1,
            "sample_rate": 8000,
            "output_format": "mp3",
        },
    )

    assert response.status_code == 400
    assert "ffmpeg" in response.json()["detail"].lower()
