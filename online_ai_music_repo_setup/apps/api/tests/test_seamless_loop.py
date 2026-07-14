from app.audio.dsp import apply_loop_crossfade


def test_loop_crossfade_reduces_boundary_difference() -> None:
    samples = [1.0] * 100 + [-1.0] * 100
    original_difference = abs(samples[0] - samples[-1])

    result = apply_loop_crossfade(
        samples=samples,
        sample_rate=100,
        crossfade_seconds=0.2,
    )

    final_difference = abs(result[0] - result[-1])

    assert final_difference < original_difference
