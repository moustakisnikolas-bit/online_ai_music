import wave
from pathlib import Path

import numpy as np
import pytest

from app.services.long_form_audio import render_long_form_wav


def _read_pcm(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        frames = wav_file.readframes(wav_file.getnframes())
    return np.frombuffer(frames, dtype="<i2").reshape(-1, channels)


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


def test_long_form_sine_is_identical_regardless_of_chunk_size(tmp_path: Path) -> None:
    small_chunks = tmp_path / "small.wav"
    large_chunks = tmp_path / "large.wav"

    for output, chunk_frames in ((small_chunks, 300), (large_chunks, 8000)):
        render_long_form_wav(
            output_path=output,
            mode="sine",
            duration_seconds=1,
            sample_rate=8000,
            amplitude=0.5,
            frequency_hz=432,
            fade_in_seconds=0.0,
            fade_out_seconds=0.0,
            chunk_frames=chunk_frames,
        )

    assert np.array_equal(_read_pcm(small_chunks), _read_pcm(large_chunks))


def test_long_form_brown_noise_deterministic_across_chunk_sizes(tmp_path: Path) -> None:
    small_chunks = tmp_path / "small.wav"
    large_chunks = tmp_path / "large.wav"

    for output, chunk_frames in ((small_chunks, 400), (large_chunks, 8000)):
        render_long_form_wav(
            output_path=output,
            mode="brown_noise",
            duration_seconds=1,
            sample_rate=8000,
            amplitude=0.5,
            seed=7,
            fade_in_seconds=0.0,
            fade_out_seconds=0.0,
            chunk_frames=chunk_frames,
        )

    assert np.array_equal(_read_pcm(small_chunks), _read_pcm(large_chunks))


def test_long_form_brown_noise_without_seed_does_not_error_or_clip(tmp_path: Path) -> None:
    output = tmp_path / "unseeded.wav"

    render_long_form_wav(
        output_path=output,
        mode="brown_noise",
        duration_seconds=2,
        sample_rate=8000,
        amplitude=0.6,
        seed=None,
        fade_in_seconds=0.0,
        fade_out_seconds=0.0,
        chunk_frames=333,
    )

    pcm = _read_pcm(output)
    peak_ratio = np.max(np.abs(pcm)) / 32767
    assert peak_ratio == pytest.approx(0.6, abs=0.01)


def test_long_form_brown_noise_reaches_requested_amplitude(tmp_path: Path) -> None:
    output = tmp_path / "brown_peak.wav"
    amplitude = 0.6

    render_long_form_wav(
        output_path=output,
        mode="brown_noise",
        duration_seconds=5,
        sample_rate=8000,
        amplitude=amplitude,
        seed=123,
        fade_in_seconds=0.0,
        fade_out_seconds=0.0,
        chunk_frames=512,
    )

    pcm = _read_pcm(output)
    peak_ratio = np.max(np.abs(pcm)) / 32767
    assert peak_ratio == pytest.approx(amplitude, abs=0.01)


def test_long_form_brown_noise_never_exceeds_full_scale(tmp_path: Path) -> None:
    output = tmp_path / "brown.wav"

    render_long_form_wav(
        output_path=output,
        mode="brown_noise",
        duration_seconds=5,
        sample_rate=8000,
        amplitude=0.95,
        seed=123,
        fade_in_seconds=0.0,
        fade_out_seconds=0.0,
        chunk_frames=512,
    )

    pcm = _read_pcm(output)
    assert np.max(np.abs(pcm)) <= 32767


def test_long_form_fade_in_and_out_reach_silence_at_edges(tmp_path: Path) -> None:
    output = tmp_path / "faded.wav"

    render_long_form_wav(
        output_path=output,
        mode="sine",
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.5,
        frequency_hz=432,
        fade_in_seconds=0.1,
        fade_out_seconds=0.1,
        chunk_frames=8000,
    )

    pcm = _read_pcm(output)
    assert pcm[0][0] == 0
    assert abs(int(pcm[-1][0])) < 50
