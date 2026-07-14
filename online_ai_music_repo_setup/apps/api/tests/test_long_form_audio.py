import wave
from pathlib import Path

from app.services.long_form_audio import render_long_form_wav


def test_long_form_sine_has_exact_frame_count(tmp_path: Path) -> None:
    output = tmp_path / "long.wav"

    render_long_form_wav(
        output_path=output,
        mode="sine",
        duration_seconds=2,
        sample_rate=8000,
        amplitude=0.1,
        channels=1,
        frequency_hz=432,
        chunk_frames=1024,
    )

    with wave.open(str(output), "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getframerate() == 8000
        assert wav_file.getnframes() == 16000


def test_long_form_binaural_is_stereo(tmp_path: Path) -> None:
    output = tmp_path / "binaural.wav"

    render_long_form_wav(
        output_path=output,
        mode="binaural_beats",
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.1,
        channels=2,
        left_frequency_hz=200,
        right_frequency_hz=210,
        chunk_frames=512,
    )

    with wave.open(str(output), "rb") as wav_file:
        assert wav_file.getnchannels() == 2
        assert wav_file.getnframes() == 8000


def test_progress_callback_reaches_completion(tmp_path: Path) -> None:
    values: list[float] = []

    render_long_form_wav(
        output_path=tmp_path / "progress.wav",
        mode="white_noise",
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.1,
        chunk_frames=1000,
        seed=42,
        progress_callback=values.append,
    )

    assert values
    assert values[-1] == 1.0
    assert all(0 < value <= 1.0 for value in values)
