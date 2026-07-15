import numpy as np

from app.audio.validation import (
    detect_clipping,
    detect_excessive_high_frequency_energy,
    detect_long_silence,
    detect_loop_seam_discontinuity,
    detect_sudden_loudness_jumps,
    validate_audio,
)


def _sine(frequency_hz: float, duration_seconds: float, sample_rate: int, amplitude: float) -> np.ndarray:
    t = np.arange(int(duration_seconds * sample_rate)) / sample_rate
    return (amplitude * np.sin(2.0 * np.pi * frequency_hz * t)).astype(np.float32)


def test_detect_clipping_true_for_full_scale() -> None:
    samples = np.full(1000, 1.0, dtype=np.float32)
    assert detect_clipping(samples) is True


def test_detect_clipping_false_for_normal_signal() -> None:
    samples = _sine(440, 1, 44100, 0.3)
    assert detect_clipping(samples) is False


def test_detect_long_silence_true_for_extended_zeros() -> None:
    samples = np.zeros(44100 * 10, dtype=np.float32)
    assert detect_long_silence(samples, 44100) is True


def test_detect_long_silence_false_for_normal_signal() -> None:
    samples = _sine(440, 10, 44100, 0.3)
    assert detect_long_silence(samples, 44100) is False


def test_detect_long_silence_false_for_brief_silence() -> None:
    samples = np.concatenate(
        [_sine(440, 2, 44100, 0.3), np.zeros(44100, dtype=np.float32), _sine(440, 2, 44100, 0.3)]
    )
    assert detect_long_silence(samples, 44100, min_silence_seconds=5.0) is False


def test_detect_sudden_loudness_jumps_true_for_abrupt_change() -> None:
    quiet = _sine(440, 2, 44100, 0.01)
    loud = _sine(440, 2, 44100, 0.9)
    samples = np.concatenate([quiet, loud])
    assert detect_sudden_loudness_jumps(samples, 44100) is True


def test_detect_sudden_loudness_jumps_false_for_steady_signal() -> None:
    samples = _sine(440, 4, 44100, 0.3)
    assert detect_sudden_loudness_jumps(samples, 44100) is False


def test_detect_excessive_high_frequency_energy_true_for_high_tone() -> None:
    samples = _sine(15000, 2, 44100, 0.5)
    assert detect_excessive_high_frequency_energy(samples, 44100) is True


def test_detect_excessive_high_frequency_energy_false_for_low_tone() -> None:
    samples = _sine(200, 2, 44100, 0.5)
    assert detect_excessive_high_frequency_energy(samples, 44100) is False


def test_detect_loop_seam_discontinuity_true_for_mismatched_edges() -> None:
    samples = np.array([0.8, 0.1, 0.1, -0.9], dtype=np.float32)
    assert detect_loop_seam_discontinuity(samples) is True


def test_detect_loop_seam_discontinuity_false_for_matching_edges() -> None:
    samples = np.array([0.1, 0.5, 0.5, 0.1], dtype=np.float32)
    assert detect_loop_seam_discontinuity(samples) is False


def test_validate_audio_reports_multiple_issues() -> None:
    clipped_and_silent = np.concatenate(
        [np.full(1000, 1.0, dtype=np.float32), np.zeros(44100 * 10, dtype=np.float32)]
    )
    report = validate_audio(clipped_and_silent, 44100)

    assert not report.passed
    assert "clipping detected" in report.issues
    assert "long digital silence detected" in report.issues


def test_validate_audio_passes_for_clean_signal() -> None:
    samples = _sine(440, 2, 44100, 0.3)
    report = validate_audio(samples, 44100)

    assert report.passed
    assert report.issues == []


def test_validate_audio_checks_loop_seam_only_when_requested() -> None:
    samples = np.array([0.9, 0.0, 0.0, -0.9] * 100, dtype=np.float32)

    without_check = validate_audio(samples, 44100, check_loop_seam=False)
    with_check = validate_audio(samples, 44100, check_loop_seam=True)

    assert "audible loop boundary discontinuity detected" not in without_check.issues
    assert "audible loop boundary discontinuity detected" in with_check.issues
