import numpy as np

from app.services.audio_generator import _apply_sidechain_ducking


def _burst_track(sample_rate: int, total_seconds: float, burst_start: float, burst_seconds: float, seed: int) -> np.ndarray:
    n = int(sample_rate * total_seconds)
    samples = np.zeros(n, dtype=np.float32)
    start = int(burst_start * sample_rate)
    length = int(burst_seconds * sample_rate)
    rng = np.random.default_rng(seed)
    samples[start : start + length] = rng.uniform(-1.0, 1.0, length).astype(np.float32)
    return samples


def test_no_trigger_tracks_returns_none() -> None:
    assert _apply_sidechain_ducking([], sample_rate=44100) is None


def test_trigger_track_ducks_a_constant_base() -> None:
    sr = 44100
    trigger = _burst_track(sr, total_seconds=3.0, burst_start=1.0, burst_seconds=0.3, seed=1)
    base = np.full(len(trigger), 0.2, dtype=np.float32)

    envelope = _apply_sidechain_ducking([(trigger, 1.0)], sample_rate=sr)

    assert envelope is not None
    ducked_base = base * envelope

    before = ducked_base[: int(0.9 * sr)]
    during = ducked_base[int(1.05 * sr) : int(1.2 * sr)]

    assert np.mean(before) == np.mean(np.full_like(before, 0.2))  # untouched before the event
    assert np.mean(during) < np.mean(before)  # measurably reduced during the event


def test_multiple_triggers_combine_via_minimum_not_multiplication() -> None:
    sr = 44100
    total = 3.0
    trigger_a = _burst_track(sr, total, burst_start=1.0, burst_seconds=0.3, seed=1)
    trigger_b = _burst_track(sr, total, burst_start=1.0, burst_seconds=0.3, seed=2)  # same window

    combined = _apply_sidechain_ducking(
        [(trigger_a, 1.0), (trigger_b, 1.0)], sample_rate=sr
    )
    single = _apply_sidechain_ducking([(trigger_a, 1.0)], sample_rate=sr)

    assert combined is not None and single is not None
    # Overlapping triggers duck at most as hard as either alone (np.minimum
    # picking the deeper of the two), never deeper via multiplicative
    # stacking.
    window = slice(int(1.05 * sr), int(1.2 * sr))
    assert np.min(combined[window]) >= 0.4 - 1e-3
