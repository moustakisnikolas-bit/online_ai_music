import struct
import wave
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.audio.sample_library import NaturalSoundSample
from app.audio.types import AudioMode, ChannelMode
from app.services import audio_generator
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


def test_generate_mixed_ambient_scene_with_waves_and_birds(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="Coastal Morning",
        mode=AudioMode.MIXED_AMBIENT,
        channels=ChannelMode.STEREO,
        ambient_layers=[
            {"kind": "texture", "texture_type": "waves", "gain": 0.6},
            {"kind": "texture", "texture_type": "birds", "gain": 0.3},
        ],
        duration_seconds=2,
        sample_rate=8000,
        amplitude=0.1,
        fade_in_seconds=0,
        fade_out_seconds=0,
        seed=3,
    )

    result = generate_audio(request, tmp_path)

    assert result.mode == "mixed_ambient"

    with wave.open(result.file_path, "rb") as wav_file:
        assert wav_file.getnchannels() == 2
        assert wav_file.getnframes() == 16000


def test_generate_mixed_ambient_scene_with_all_eight_textures(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="Everything At Once",
        mode=AudioMode.MIXED_AMBIENT,
        channels=ChannelMode.MONO,
        ambient_layers=[
            {"kind": "texture", "texture_type": "rain", "gain": 0.15},
            {"kind": "texture", "texture_type": "wind", "gain": 0.15},
            {"kind": "texture", "texture_type": "waves", "gain": 0.15},
            {"kind": "texture", "texture_type": "birds", "gain": 0.1},
            {"kind": "texture", "texture_type": "fire", "gain": 0.15},
            {"kind": "texture", "texture_type": "water", "gain": 0.15},
            {"kind": "texture", "texture_type": "thunder", "gain": 0.1},
            {"kind": "texture", "texture_type": "chimes", "gain": 0.1},
        ],
        duration_seconds=2,
        sample_rate=8000,
        amplitude=0.1,
        fade_in_seconds=0,
        fade_out_seconds=0,
        seed=11,
    )

    result = generate_audio(request, tmp_path)

    with wave.open(result.file_path, "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getnframes() == 16000


def test_generate_mixed_ambient_scene_with_sample_layer(tmp_path: Path, monkeypatch) -> None:
    sample_audio_path = tmp_path / "rain-01.wav"

    with wave.open(str(sample_audio_path), "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(8000)
        frames = bytearray()

        for index in range(2000):
            value = int(8000 * ((index % 40) / 40 - 0.5))
            frames.extend(struct.pack("<h", value))

        wav_file.writeframes(bytes(frames))

    sample = NaturalSoundSample(
        id="rain-01",
        label="Rain",
        category="rain",
        filename="rain-01.wav",
        license="CC0",
    )

    monkeypatch.setattr(audio_generator, "get_sample", lambda sample_id: sample)
    monkeypatch.setattr(
        audio_generator,
        "resolve_sample_audio_path",
        lambda _sample: sample_audio_path,
    )

    request = AudioGenerationRequest(
        title="Sampled Rain",
        mode=AudioMode.MIXED_AMBIENT,
        channels=ChannelMode.MONO,
        ambient_layers=[
            {"kind": "sample", "sample_id": "rain-01", "gain": 0.8},
            {"kind": "noise", "noise_type": "brown_noise", "gain": 0.3},
        ],
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.1,
        fade_in_seconds=0,
        fade_out_seconds=0,
        seed=1,
    )

    result = generate_audio(request, tmp_path / "output")

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


@pytest.mark.parametrize("noise_type", ["white_noise", "pink_noise", "brown_noise", "blue_noise", "violet_noise"])
def test_ambient_noise_layer_accepts_every_real_noise_color(noise_type: str, tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="Noise Color Smoke Test",
        mode=AudioMode.MIXED_AMBIENT,
        ambient_layers=[{"kind": "noise", "noise_type": noise_type, "gain": 0.5}],
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.2,
        fade_in_seconds=0,
        fade_out_seconds=0,
    )

    result = generate_audio(request, tmp_path)

    with wave.open(result.file_path, "rb") as wav_file:
        assert wav_file.getnframes() == 8000


def test_ambient_noise_layer_rejects_a_non_noise_audio_mode() -> None:
    with pytest.raises(ValidationError):
        AudioGenerationRequest(
            title="Invalid Noise Type",
            mode=AudioMode.MIXED_AMBIENT,
            ambient_layers=[
                {"kind": "noise", "noise_type": "sine", "gain": 0.2},
            ],
            duration_seconds=1,
            sample_rate=8000,
        )
