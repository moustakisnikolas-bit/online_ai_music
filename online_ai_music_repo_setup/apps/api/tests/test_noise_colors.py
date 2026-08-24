import numpy as np

from app.audio.dsp import (
    generate_blue_noise,
    generate_brown_noise,
    generate_pink_noise,
    generate_violet_noise,
    generate_white_noise,
)


def _high_to_low_energy_ratio(samples: np.ndarray, sample_rate: int) -> float:
    spectrum = np.abs(np.fft.rfft(samples)) ** 2
    midpoint = len(spectrum) // 2
    low_energy = spectrum[1:midpoint].sum()  # skip DC bin
    high_energy = spectrum[midpoint:].sum()
    return float(high_energy / low_energy)


def test_generate_blue_noise_has_correct_length_and_range() -> None:
    samples = generate_blue_noise(duration_seconds=2, sample_rate=8000, amplitude=0.3, seed=1)

    assert len(samples) == 16000
    assert float(samples.max()) <= 0.3 + 1e-6
    assert float(samples.min()) >= -0.3 - 1e-6
    assert float(samples.std()) > 0.0


def test_generate_violet_noise_has_correct_length_and_range() -> None:
    samples = generate_violet_noise(duration_seconds=2, sample_rate=8000, amplitude=0.3, seed=1)

    assert len(samples) == 16000
    assert float(samples.max()) <= 0.3 + 1e-6
    assert float(samples.min()) >= -0.3 - 1e-6
    assert float(samples.std()) > 0.0


def test_generate_blue_and_violet_noise_are_deterministic_for_a_given_seed() -> None:
    assert (generate_blue_noise(2, 8000, 0.3, seed=7) == generate_blue_noise(2, 8000, 0.3, seed=7)).all()
    assert (generate_violet_noise(2, 8000, 0.3, seed=7) == generate_violet_noise(2, 8000, 0.3, seed=7)).all()


def test_noise_colors_have_real_distinct_spectral_tilt() -> None:
    """Proves these are actually different-sounding noise colors, not
    just five different random-number generators -- brown (-6dB/oct)
    through violet (+6dB/oct) should show a strictly increasing amount
    of high-frequency energy relative to low-frequency energy.
    """
    sample_rate = 44100
    duration = 3
    seed = 42

    ratios = {
        "brown": _high_to_low_energy_ratio(
            generate_brown_noise(duration, sample_rate, 0.9, seed), sample_rate
        ),
        "pink": _high_to_low_energy_ratio(
            generate_pink_noise(duration, sample_rate, 0.9, seed), sample_rate
        ),
        "white": _high_to_low_energy_ratio(
            generate_white_noise(duration, sample_rate, 0.9, seed), sample_rate
        ),
        "blue": _high_to_low_energy_ratio(
            generate_blue_noise(duration, sample_rate, 0.9, seed), sample_rate
        ),
        "violet": _high_to_low_energy_ratio(
            generate_violet_noise(duration, sample_rate, 0.9, seed), sample_rate
        ),
    }

    assert ratios["brown"] < ratios["pink"] < ratios["white"] < ratios["blue"] < ratios["violet"]
