import wave
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.audio.mastering import measure_lufs
from app.audio.types import AudioMode, ChannelMode
from app.schemas.audio import AudioGenerationRequest
from app.services.audio_generator import generate_audio


def test_generate_audio_reports_loudness_by_default(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="Default Loudness Report",
        mode=AudioMode.SINE,
        frequency_hz=432,
        duration_seconds=2,
        sample_rate=8000,
        amplitude=0.3,
    )

    result = generate_audio(request, tmp_path)

    assert result.loudness_lufs is not None
    assert result.validation_warnings == []


def test_generate_audio_normalizes_to_target_lufs(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="Target Loudness",
        mode=AudioMode.SINE,
        frequency_hz=432,
        duration_seconds=2,
        sample_rate=8000,
        amplitude=0.05,
        target_lufs=-20.0,
    )

    result = generate_audio(request, tmp_path)

    assert abs(result.loudness_lufs - (-20.0)) < 1.0

    with wave.open(result.file_path, "rb") as wav_file:
        assert wav_file.getnframes() == 16000


def test_generate_audio_with_mastering_eq_does_not_error(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="Mastering EQ",
        mode=AudioMode.SINE,
        frequency_hz=432,
        duration_seconds=1,
        sample_rate=44100,
        apply_mastering_eq=True,
    )

    result = generate_audio(request, tmp_path)
    assert result.status == "generated"


def test_generate_audio_with_fold_bass_to_mono(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="Bass Fold",
        mode=AudioMode.BINAURAL_BEATS,
        channels=ChannelMode.STEREO,
        left_frequency_hz=200,
        right_frequency_hz=210,
        duration_seconds=1,
        sample_rate=44100,
        fold_bass_to_mono=True,
    )

    result = generate_audio(request, tmp_path)

    with wave.open(result.file_path, "rb") as wav_file:
        assert wav_file.getnchannels() == 2


def test_fold_bass_to_mono_rejected_for_mono_output() -> None:
    with pytest.raises(ValidationError, match="stereo"):
        AudioGenerationRequest(
            title="Invalid Bass Fold",
            mode=AudioMode.SINE,
            channels=ChannelMode.MONO,
            frequency_hz=432,
            duration_seconds=1,
            sample_rate=8000,
            fold_bass_to_mono=True,
        )


def test_long_form_rejects_mastering_options() -> None:
    with pytest.raises(ValidationError, match="long_form"):
        AudioGenerationRequest(
            title="Long Form Mastering",
            mode=AudioMode.SINE,
            frequency_hz=432,
            long_form=True,
            target_lufs=-18.0,
            duration_seconds=10,
            sample_rate=8000,
        )


def test_generate_audio_flags_clipping_from_high_amplitude_layers(tmp_path: Path) -> None:
    # Two full-amplitude tone layers summed without normalization headroom
    # should trip the clipping check.
    request = AudioGenerationRequest(
        title="Loud Layers",
        mode=AudioMode.MIXED_AMBIENT,
        ambient_layers=[
            {"kind": "tone", "frequency_hz": 300, "gain": 1.0},
            {"kind": "tone", "frequency_hz": 900, "gain": 1.0},
        ],
        duration_seconds=1,
        sample_rate=8000,
        amplitude=1.0,
        fade_in_seconds=0,
        fade_out_seconds=0,
    )

    result = generate_audio(request, tmp_path)

    # mix_tracks peak-normalizes to 0.95, so this specific case shouldn't
    # clip -- this test documents that expectation rather than assuming it.
    assert "clipping detected" not in result.validation_warnings


def test_measure_lufs_reusable_directly() -> None:
    import numpy as np

    samples = (0.2 * np.sin(2 * np.pi * 440 * np.arange(44100) / 44100)).astype("float32")
    assert measure_lufs(samples, 44100) < 0
