import wave
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

client = TestClient(app)


def test_asset_metadata_and_download(tmp_path: Path) -> None:
    settings = get_settings()
    original_dir = settings.generated_audio_dir
    settings.generated_audio_dir = str(tmp_path)

    path = tmp_path / "api-test.wav"

    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(8000)
        wav_file.writeframes(b"\x00\x00" * 8000)

    try:
        metadata_response = client.get(
            "/api/v1/audio/assets/api-test.wav"
        )

        assert metadata_response.status_code == 200
        payload = metadata_response.json()
        assert payload["filename"] == "api-test.wav"
        assert payload["sample_rate"] == 8000
        assert payload["duration_seconds"] == 1.0

        download_response = client.get(
            "/api/v1/audio/assets/api-test.wav/download"
        )

        assert download_response.status_code == 200
        assert download_response.headers["content-type"].startswith("audio/wav")
        assert len(download_response.content) > 44
    finally:
        settings.generated_audio_dir = original_dir
