import numpy as np
import pytest

from app.audio.dsp import compute_duck_envelope


def _burst_signal(sample_rate: int, total_seconds: float, burst_start: float, burst_seconds: float, seed: int = 1) -> np.ndarray:
    n = int(sample_rate * total_seconds)
    samples = np.zeros(n, dtype=np.float32)
    start = int(burst_start * sample_rate)
    length = int(burst_seconds * sample_rate)
    rng = np.random.default_rng(seed)
    samples[start : start + length] = rng.uniform(-1.0, 1.0, length).astype(np.float32)
    return samples


def test_envelope_stays_flat_before_the_burst() -> None:
    sr = 44100
    signal = _burst_signal(sr, total_seconds=2.0, burst_start=1.0, burst_seconds=0.05)

    envelope = compute_duck_envelope(signal, sr)

    # Guards specifically against the lfilter-initial-condition fade-in
    # bug: an unseeded filter would ramp up from 0 at t=0 regardless of
    # there being no event there.
    assert envelope[0] == pytest.approx(1.0, abs=1e-3)
    assert np.min(envelope[: int(0.9 * sr)]) > 0.99


def test_envelope_dips_during_the_burst_and_recovers() -> None:
    sr = 44100
    burst_start = 1.0
    burst_seconds = 0.05
    signal = _burst_signal(sr, total_seconds=3.0, burst_start=burst_start, burst_seconds=burst_seconds)

    envelope = compute_duck_envelope(signal, sr, duck_depth=0.6)

    during_start = int(burst_start * sr)
    during_end = during_start + int(burst_seconds * sr)
    assert np.min(envelope[during_start:during_end]) < 0.7

    well_after = int((burst_start + burst_seconds + 1.0) * sr)
    assert envelope[well_after] > 0.95


def test_envelope_bounded_within_duck_depth_range() -> None:
    sr = 44100
    signal = _burst_signal(sr, total_seconds=1.0, burst_start=0.3, burst_seconds=0.05)

    envelope = compute_duck_envelope(signal, sr, duck_depth=0.6)

    assert np.all(envelope >= 0.4 - 1e-3)
    assert np.all(envelope <= 1.0 + 1e-6)


def test_envelope_has_no_false_positives_on_steady_noise() -> None:
    sr = 44100
    rng = np.random.default_rng(2)
    steady = rng.uniform(-0.3, 0.3, sr * 2).astype(np.float32)

    envelope = compute_duck_envelope(steady, sr)

    assert np.min(envelope) > 0.99


def test_shorter_release_recovers_faster_than_longer_release() -> None:
    sr = 44100
    burst_start = 0.5
    # Long enough that both release_seconds settings dip to a comparable
    # depth during the event itself -- a burst shorter than (or close to)
    # release_seconds would confound "recovers faster" with "never dipped
    # as deeply in the first place" (a slow filter barely reacts to a
    # brief transient at all), which isn't what this test is checking.
    burst_seconds = 1.0
    signal = _burst_signal(sr, total_seconds=4.0, burst_start=burst_start, burst_seconds=burst_seconds)

    short_release = compute_duck_envelope(signal, sr, release_seconds=0.1)
    long_release = compute_duck_envelope(signal, sr, release_seconds=0.6)

    check_at = int((burst_start + burst_seconds + 0.2) * sr)
    assert short_release[check_at] > long_release[check_at]


def test_envelope_on_silence_returns_all_ones() -> None:
    sr = 44100
    silence = np.zeros(sr, dtype=np.float32)

    envelope = compute_duck_envelope(silence, sr)

    assert np.all(envelope == 1.0)


def test_envelope_output_length_and_dtype() -> None:
    sr = 44100
    signal = _burst_signal(sr, total_seconds=1.5, burst_start=0.5, burst_seconds=0.05)

    envelope = compute_duck_envelope(signal, sr)

    assert len(envelope) == len(signal)
    assert envelope.dtype == np.float32
