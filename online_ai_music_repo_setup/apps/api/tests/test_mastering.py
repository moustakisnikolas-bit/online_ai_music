import numpy as np

from app.audio.mastering import (
    apply_mastering_eq,
    apply_reverb,
    fold_bass_to_mono,
    limit_true_peak,
    measure_lufs,
    normalize_to_lufs,
    true_peak_dbtp,
)


def _sine(frequency_hz: float, duration_seconds: float, sample_rate: int, amplitude: float) -> np.ndarray:
    t = np.arange(int(duration_seconds * sample_rate)) / sample_rate
    return (amplitude * np.sin(2.0 * np.pi * frequency_hz * t)).astype(np.float32)


def test_measure_lufs_returns_a_plausible_value() -> None:
    samples = _sine(440, 3, 44100, 0.2)
    lufs = measure_lufs(samples, 44100)

    assert np.isfinite(lufs)
    assert -40 < lufs < 0


def test_normalize_to_lufs_hits_target() -> None:
    samples = _sine(440, 3, 44100, 0.05)
    normalized = normalize_to_lufs(samples, 44100, target_lufs=-18.0)

    result_lufs = measure_lufs(normalized, 44100)
    assert abs(result_lufs - (-18.0)) < 0.5


def test_normalize_to_lufs_is_a_no_op_for_silence() -> None:
    samples = np.zeros(44100, dtype=np.float32)
    normalized = normalize_to_lufs(samples, 44100, target_lufs=-18.0)

    assert np.allclose(normalized, 0.0)


def test_true_peak_dbtp_matches_full_scale_sine() -> None:
    samples = _sine(1000, 1, 44100, 1.0)
    dbtp = true_peak_dbtp(samples)

    # A full-scale sine's true peak should be close to 0 dBTP (allow
    # headroom for oversampling ringing near the peak).
    assert -1.0 < dbtp < 1.0


def test_limit_true_peak_brings_signal_under_target() -> None:
    samples = _sine(1000, 1, 44100, 1.0)
    limited = limit_true_peak(samples, target_dbtp=-3.0)

    assert true_peak_dbtp(limited) <= -3.0 + 0.2


def test_limit_true_peak_is_a_no_op_when_already_under_target() -> None:
    samples = _sine(1000, 1, 44100, 0.1)
    limited = limit_true_peak(samples, target_dbtp=-1.0)

    assert np.allclose(limited, samples, atol=1e-6)


def test_apply_mastering_eq_preserves_length_and_range() -> None:
    samples = _sine(440, 2, 44100, 0.3)
    shaped = apply_mastering_eq(samples, 44100)

    assert len(shaped) == len(samples)
    assert float(np.max(np.abs(shaped))) < 2.0  # no wild filter blowup


def test_apply_mastering_eq_handles_low_sample_rate_without_error() -> None:
    # 8000 Hz is used heavily in the rest of the test suite; the 8kHz
    # peaking band would exceed Nyquist there and must be skipped, not
    # raise.
    samples = _sine(440, 1, 8000, 0.3)
    shaped = apply_mastering_eq(samples, 8000)

    assert len(shaped) == len(samples)


def test_apply_reverb_extends_energy_past_the_dry_signal() -> None:
    # An impulse (spike + silence) fed through a fully-wet reverb should
    # have audible energy after the spike, where the dry signal has none --
    # proof the convolution actually happened, not just a level change.
    impulse = np.zeros(44100, dtype=np.float32)
    impulse[100] = 1.0

    wet = apply_reverb(impulse, 44100, decay_seconds=1.0, wet_level=1.0, seed=1)

    tail = wet[5000:20000]
    assert float(np.max(np.abs(tail))) > 1e-4


def test_apply_reverb_wet_level_zero_is_a_no_op() -> None:
    samples = _sine(440, 1, 44100, 0.3)
    result = apply_reverb(samples, 44100, wet_level=0.0)

    assert np.allclose(result, samples)


def test_apply_reverb_is_deterministic_for_a_given_seed() -> None:
    samples = _sine(440, 1, 44100, 0.3)

    first = apply_reverb(samples, 44100, seed=7)
    second = apply_reverb(samples, 44100, seed=7)

    assert np.array_equal(first, second)


def test_apply_reverb_preserves_length() -> None:
    samples = _sine(440, 2, 44100, 0.3)
    wet = apply_reverb(samples, 44100, decay_seconds=3.0, wet_level=0.5)

    assert len(wet) == len(samples)


def test_fold_bass_to_mono_makes_low_frequencies_identical() -> None:
    # A pure 40 Hz tone (well below the 120 Hz cutoff) panned differently
    # per channel should come out close to identical in both channels
    # after bass mono-folding, once the IIR filter's startup transient has
    # settled (checked past the first 0.1s -- zero-initial-condition
    # filtering always has a brief transient at t=0, which is negligible
    # in practice but too large for a tight tolerance right at the start).
    left = _sine(40, 1, 44100, 0.5)
    right = _sine(40, 1, 44100, 0.2)

    new_left, new_right = fold_bass_to_mono(left, right, 44100, cutoff_hz=120.0)

    settled = slice(int(0.1 * 44100), None)
    assert np.allclose(new_left[settled], new_right[settled], atol=0.01)
