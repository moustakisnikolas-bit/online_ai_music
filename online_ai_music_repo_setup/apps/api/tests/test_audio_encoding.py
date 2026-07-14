from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.audio_encoding import encode_audio


def test_wav_encoding_returns_original_path(tmp_path: Path) -> None:
    source = tmp_path / "source.wav"
    source.write_bytes(b"RIFF")

    assert encode_audio(source, "wav") == source


def test_encoded_format_requires_ffmpeg(tmp_path: Path) -> None:
    source = tmp_path / "source.wav"
    source.write_bytes(b"RIFF")

    with patch(
        "app.services.audio_encoding.ffmpeg_available",
        return_value=False,
    ):
        with pytest.raises(RuntimeError, match="FFmpeg is required"):
            encode_audio(source, "mp3")


def test_unknown_format_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source.wav"
    source.write_bytes(b"RIFF")

    with pytest.raises(ValueError, match="Unsupported output format"):
        encode_audio(source, "aac")
