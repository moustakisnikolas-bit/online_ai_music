import wave
from pathlib import Path

import pytest

from app.audio.types import AudioMode, ChannelMode
from app.schemas.audio import AudioGenerationRequest
from app.services.audio_generator import generate_audio


def test_binaural_requires_stereo() -> None:
    with pytest.raises(ValueError):
        AudioGenerationRequest(
            title="Invalid Binaural",
            mode=AudioMode.BINAURAL_BEATS,
            channels=ChannelMode.MONO,
            left_frequency_hz=200,
            right_frequency_hz=210,
            duration_seconds=1,
            sample_rate=8000,
        )


def test_generate_binaural_stereo(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="Alpha Binaural",
        mode=AudioMode.BINAURAL_BEATS,
        channels=ChannelMode.STEREO,
        left_frequency_hz=200,
        right_frequency_hz=210,
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.1,
        fade_in_seconds=0,
        fade_out_seconds=0,
    )

    result = generate_audio(request, tmp_path)

    with wave.open(result.file_path, "rb") as wav_file:
        assert wav_file.getnchannels() == 2
        assert wav_file.getframerate() == 8000
        assert wav_file.getnframes() == 8000


def test_generate_isochronic_tone(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="Alpha Isochronic",
        mode=AudioMode.ISOCHRONIC_TONES,
        channels=ChannelMode.MONO,
        frequency_hz=220,
        pulse_frequency_hz=10,
        modulation_depth=1.0,
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.1,
        fade_in_seconds=0,
        fade_out_seconds=0,
    )

    result = generate_audio(request, tmp_path)

    assert result.frequency_hz == 220

    with wave.open(result.file_path, "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getnframes() == 8000
