from pathlib import Path

from app.audio.types import AudioMode
from app.schemas.audio import AudioGenerationRequest
from app.services.audio_generator import generate_audio


def test_sine_response_includes_frequency(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="432 Hz Compatibility Test",
        mode=AudioMode.SINE,
        frequency_hz=432,
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.1,
    )

    result = generate_audio(request, tmp_path)

    assert result.frequency_hz == 432


def test_noise_response_has_no_single_frequency(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="Brown Noise Compatibility Test",
        mode=AudioMode.BROWN_NOISE,
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.1,
        fade_in_seconds=0,
        fade_out_seconds=0,
        seed=42,
    )

    result = generate_audio(request, tmp_path)

    assert result.frequency_hz is None
