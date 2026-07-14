import wave
from pathlib import Path

from app.audio.types import AudioMode
from app.schemas.audio import AudioGenerationRequest, ToneLayerRequest
from app.services.audio_generator import generate_audio


def assert_wav(path: Path, sample_rate: int, frames: int) -> None:
    assert path.exists()

    with wave.open(str(path), "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getframerate() == sample_rate
        assert wav_file.getnframes() == frames


def test_generate_white_noise(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="White Noise",
        mode=AudioMode.WHITE_NOISE,
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.1,
        fade_in_seconds=0,
        fade_out_seconds=0,
        seed=42,
    )

    result = generate_audio(request, tmp_path)

    assert result.mode == "white_noise"
    assert_wav(Path(result.file_path), 8000, 8000)


def test_generate_layered_tones(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="Layered Calm",
        mode=AudioMode.LAYERED_TONES,
        layers=[
            ToneLayerRequest(frequency_hz=432, amplitude=0.1),
            ToneLayerRequest(frequency_hz=216, amplitude=0.05),
        ],
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.2,
        fade_in_seconds=0,
        fade_out_seconds=0,
    )

    result = generate_audio(request, tmp_path)

    assert result.mode == "layered_tones"
    assert_wav(Path(result.file_path), 8000, 8000)


def test_generate_preset(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="Deep Brown",
        mode=AudioMode.PRESET,
        preset_name="deep-brown",
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.2,
        fade_in_seconds=0,
        fade_out_seconds=0,
        seed=123,
    )

    result = generate_audio(request, tmp_path)

    assert result.mode == "preset"
    assert_wav(Path(result.file_path), 8000, 8000)
