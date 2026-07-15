import wave
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.audio.types import AudioMode, ChannelMode
from app.schemas.audio import AudioGenerationRequest
from app.services.audio_generator import generate_audio


def test_generate_mixed_ambient_scene(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="Rain and Brown Noise",
        mode=AudioMode.MIXED_AMBIENT,
        channels=ChannelMode.STEREO,
        ambient_layers=[
            {"kind": "noise", "noise_type": "brown_noise", "gain": 0.7},
            {"kind": "tone", "frequency_hz": 432, "gain": 0.2},
            {"kind": "texture", "texture_type": "rain", "gain": 0.2},
        ],
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.1,
        fade_in_seconds=0,
        fade_out_seconds=0,
        seed=42,
    )

    result = generate_audio(request, tmp_path)

    assert result.mode == "mixed_ambient"

    with wave.open(result.file_path, "rb") as wav_file:
        assert wav_file.getnchannels() == 2
        assert wav_file.getframerate() == 8000
        assert wav_file.getnframes() == 8000


def test_generate_mixed_ambient_scene_with_many_layers(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="Layered Night Scene",
        mode=AudioMode.MIXED_AMBIENT,
        channels=ChannelMode.MONO,
        ambient_layers=[
            {"kind": "noise", "noise_type": "brown_noise", "gain": 0.4},
            {"kind": "noise", "noise_type": "pink_noise", "gain": 0.2},
            {"kind": "tone", "frequency_hz": 432, "gain": 0.15},
            {"kind": "tone", "frequency_hz": 528, "gain": 0.1},
            {"kind": "texture", "texture_type": "rain", "gain": 0.2},
            {"kind": "texture", "texture_type": "wind", "gain": 0.15},
        ],
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.1,
        fade_in_seconds=0,
        fade_out_seconds=0,
        seed=7,
    )

    result = generate_audio(request, tmp_path)

    with wave.open(result.file_path, "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getnframes() == 8000


def test_mixed_ambient_requires_at_least_one_layer() -> None:
    with pytest.raises(ValidationError):
        AudioGenerationRequest(
            title="Empty Scene",
            mode=AudioMode.MIXED_AMBIENT,
            ambient_layers=[],
            duration_seconds=1,
            sample_rate=8000,
        )


def test_ambient_texture_layer_rejects_none() -> None:
    with pytest.raises(ValidationError):
        AudioGenerationRequest(
            title="Invalid Texture",
            mode=AudioMode.MIXED_AMBIENT,
            ambient_layers=[
                {"kind": "texture", "texture_type": "none", "gain": 0.2},
            ],
            duration_seconds=1,
            sample_rate=8000,
        )
