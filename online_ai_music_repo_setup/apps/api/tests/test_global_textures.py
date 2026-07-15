import wave
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.audio.types import AudioMode, ChannelMode
from app.schemas.audio import AudioGenerationRequest
from app.services.audio_generator import generate_audio


def test_sine_mode_with_rain_texture(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="Sine With Rain",
        mode=AudioMode.SINE,
        frequency_hz=432,
        textures=[{"texture_type": "rain", "gain": 0.3}],
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.1,
        fade_in_seconds=0,
        fade_out_seconds=0,
    )

    result = generate_audio(request, tmp_path)

    assert result.mode == "sine"

    with wave.open(result.file_path, "rb") as wav_file:
        assert wav_file.getnframes() == 8000


def test_binaural_beats_with_texture_applies_same_bed_to_both_channels(
    tmp_path: Path,
) -> None:
    request = AudioGenerationRequest(
        title="Binaural With Waves",
        mode=AudioMode.BINAURAL_BEATS,
        channels=ChannelMode.STEREO,
        left_frequency_hz=200,
        right_frequency_hz=210,
        textures=[{"texture_type": "waves", "gain": 0.4}],
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.1,
        fade_in_seconds=0,
        fade_out_seconds=0,
        seed=5,
    )

    result = generate_audio(request, tmp_path)

    with wave.open(result.file_path, "rb") as wav_file:
        assert wav_file.getnchannels() == 2
        assert wav_file.getnframes() == 8000


def test_preset_mode_with_multiple_textures(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="Preset With Fire and Chimes",
        mode=AudioMode.PRESET,
        preset_name="deep-brown",
        textures=[
            {"texture_type": "fire", "gain": 0.3},
            {"texture_type": "chimes", "gain": 0.2},
        ],
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.1,
        fade_in_seconds=0,
        fade_out_seconds=0,
        seed=2,
    )

    result = generate_audio(request, tmp_path)

    with wave.open(result.file_path, "rb") as wav_file:
        assert wav_file.getnframes() == 8000


def test_no_textures_is_a_no_op() -> None:
    request = AudioGenerationRequest(
        title="Plain Sine",
        mode=AudioMode.SINE,
        frequency_hz=432,
        duration_seconds=1,
        sample_rate=8000,
    )

    assert request.textures == []


def test_long_form_rejects_textures() -> None:
    with pytest.raises(ValidationError, match="long_form"):
        AudioGenerationRequest(
            title="Long Form With Rain",
            mode=AudioMode.SINE,
            frequency_hz=432,
            long_form=True,
            textures=[{"texture_type": "rain", "gain": 0.3}],
            duration_seconds=10,
            sample_rate=8000,
        )
