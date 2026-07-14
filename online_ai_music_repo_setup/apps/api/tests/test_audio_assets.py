import wave
from pathlib import Path

import pytest

from app.services.audio_assets import (
    calculate_sha256,
    inspect_wav,
    safe_asset_path,
)


def create_test_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(2)
        wav_file.setsampwidth(2)
        wav_file.setframerate(8000)
        wav_file.writeframes(b"\x00\x00\x00\x00" * 8000)


def test_inspect_wav_returns_metadata(tmp_path: Path) -> None:
    path = tmp_path / "test.wav"
    create_test_wav(path)

    metadata = inspect_wav(path)

    assert metadata.filename == "test.wav"
    assert metadata.channels == 2
    assert metadata.sample_rate == 8000
    assert metadata.sample_width_bytes == 2
    assert metadata.frame_count == 8000
    assert metadata.duration_seconds == 1.0
    assert metadata.checksum_sha256 == calculate_sha256(path)


def test_safe_asset_path_accepts_simple_filename(tmp_path: Path) -> None:
    result = safe_asset_path(tmp_path, "asset.wav")

    assert result == (tmp_path / "asset.wav").resolve()


@pytest.mark.parametrize(
    "filename",
    [
        "../asset.wav",
        "nested/asset.wav",
        "/tmp/asset.wav",
        "asset.mp3",
        "",
    ],
)
def test_safe_asset_path_rejects_unsafe_names(
    tmp_path: Path,
    filename: str,
) -> None:
    with pytest.raises(ValueError):
        safe_asset_path(tmp_path, filename)
