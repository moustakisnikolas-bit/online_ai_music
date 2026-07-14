import wave
from pathlib import Path

from app.schemas.audio import AudioGenerationRequest
from app.services.audio_generator import generate_sine_wave


def test_generate_sine_wave(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="Test Tone",
        frequency_hz=432,
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.1,
    )

    result = generate_sine_wave(
        request=request,
        output_dir=tmp_path,
    )

    output_path = Path(result.file_path)

    assert output_path.exists()
    assert result.frequency_hz == 432
    assert result.duration_seconds == 1

    with wave.open(str(output_path), "r") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getframerate() == 8000
        assert wav_file.getnframes() == 8000
