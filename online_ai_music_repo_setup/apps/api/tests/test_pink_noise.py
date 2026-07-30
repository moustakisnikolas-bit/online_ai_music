import numpy as np
from scipy.signal import lfilter

from app.audio.dsp import generate_pink_noise


def _reference_pink_noise(white: np.ndarray) -> np.ndarray:
    """Independent reimplementation of Paul Kellet's original parallel
    filter bank (the pre-optimization approach: 6 separate one-pole
    `lfilter` calls summed, plus a delayed-white and a direct-white term),
    kept deliberately separate from dsp.py's combined-single-filter
    implementation so this test can catch a real frequency-response
    regression rather than just comparing the optimized code to itself.
    """
    sections = (
        (0.99886, 0.0555179),
        (0.99332, 0.0750759),
        (0.96900, 0.1538520),
        (0.86650, 0.3104856),
        (0.55000, 0.5329522),
        (-0.7616, -0.0168980),
    )

    pink = np.zeros_like(white)
    for pole, gain in sections:
        pink += lfilter([gain], [1.0, -pole], white)

    delayed_white = np.concatenate(([0.0], white[:-1])).astype(np.float32, copy=False)
    pink += delayed_white * 0.115926
    pink += white * 0.5362

    return pink


def test_generate_pink_noise_has_correct_length_and_range() -> None:
    samples = generate_pink_noise(duration_seconds=2, sample_rate=8000, amplitude=0.3, seed=1)

    assert len(samples) == 16000
    assert float(samples.max()) <= 0.3 + 1e-6
    assert float(samples.min()) >= -0.3 - 1e-6
    assert float(samples.std()) > 0.0


def test_generate_pink_noise_is_deterministic_for_a_given_seed() -> None:
    first = generate_pink_noise(2, 8000, 0.3, seed=7)
    second = generate_pink_noise(2, 8000, 0.3, seed=7)

    assert (first == second).all()


def test_generate_pink_noise_matches_original_parallel_filter_bank() -> None:
    """Pins the single-filter optimization to the original 6-section
    parallel filter bank's frequency response. Only the (unnormalized)
    filter shape needs to match -- generate_pink_noise's final
    peak-normalization step is applied after filtering, so this compares
    pre-normalization output using the same filtering math dsp.py uses
    internally, reconstructed independently above.
    """
    rng = np.random.default_rng(123)
    white = rng.uniform(-1.0, 1.0, size=200_000).astype(np.float32)

    reference = _reference_pink_noise(white)

    from app.audio.dsp import _PINK_NOISE_DENOMINATOR, _PINK_NOISE_NUMERATOR

    combined = lfilter(_PINK_NOISE_NUMERATOR, _PINK_NOISE_DENOMINATOR, white)

    max_diff = np.max(np.abs(reference.astype(np.float64) - combined))
    assert max_diff < 1e-4
