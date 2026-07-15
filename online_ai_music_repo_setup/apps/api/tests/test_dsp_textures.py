from app.audio.dsp import generate_birds_texture, generate_waves_texture


def test_generate_waves_texture_has_correct_length_and_range() -> None:
    samples = generate_waves_texture(
        duration_seconds=2,
        sample_rate=8000,
        amplitude=0.3,
        seed=1,
    )

    assert len(samples) == 16000
    assert float(samples.max()) <= 1.0
    assert float(samples.min()) >= -1.0
    assert float(samples.std()) > 0.0


def test_generate_waves_texture_is_deterministic_for_a_given_seed() -> None:
    first = generate_waves_texture(2, 8000, 0.3, seed=7)
    second = generate_waves_texture(2, 8000, 0.3, seed=7)

    assert (first == second).all()


def test_generate_birds_texture_has_correct_length_and_range() -> None:
    samples = generate_birds_texture(
        duration_seconds=5,
        sample_rate=8000,
        amplitude=0.3,
        seed=1,
    )

    assert len(samples) == 40000
    assert float(samples.max()) <= 1.0
    assert float(samples.min()) >= -1.0
    # At least one chirp should have landed somewhere in 5 seconds given
    # the 0.8-3.5s gap distribution -- the buffer shouldn't be all zeros.
    assert float(samples.std()) > 0.0


def test_generate_birds_texture_handles_very_short_duration() -> None:
    # Shorter than the minimum gap between chirps -- should return silence
    # rather than raising.
    samples = generate_birds_texture(
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.3,
        seed=123,
    )

    assert len(samples) == 8000
