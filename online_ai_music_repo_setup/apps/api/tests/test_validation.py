import numpy as np

from app.audio.validation import (
    check_combination_harmony,
    detect_clipping,
    detect_crest_factor_anomaly,
    detect_excessive_high_frequency_energy,
    detect_long_silence,
    detect_loop_seam_discontinuity,
    detect_low_frequency_buildup,
    detect_sudden_loudness_jumps,
    detect_tone_melody_beating,
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


def test_detect_tone_melody_beating_false_when_no_melody() -> None:
    assert detect_tone_melody_beating(440.0, None) is False


def test_detect_tone_melody_beating_false_for_unison() -> None:
    assert detect_tone_melody_beating(440.0, 440.0) is False


def test_detect_tone_melody_beating_false_for_octave() -> None:
    assert detect_tone_melody_beating(880.0, 440.0) is False


def test_detect_tone_melody_beating_false_for_perfect_fifth() -> None:
    fifth_hz = 440.0 * 2.0 ** (700.0 / 1200.0)
    assert detect_tone_melody_beating(fifth_hz, 440.0) is False


def test_detect_tone_melody_beating_true_for_semitone_apart() -> None:
    semitone_hz = 440.0 * 2.0 ** (100.0 / 1200.0)
    assert detect_tone_melody_beating(semitone_hz, 440.0) is True


def test_detect_crest_factor_anomaly_false_for_normal_noise() -> None:
    samples = np.random.default_rng(1).normal(0, 0.1, 44100).astype(np.float32)
    assert detect_crest_factor_anomaly(samples) is False


def test_detect_crest_factor_anomaly_true_for_square_wave() -> None:
    # A square wave's peak equals its RMS exactly (crest factor 0dB) --
    # the clearest possible "too low" case (multiple full-level layers
    # stacking with no headroom looks like this).
    samples = np.array([0.5, -0.5] * 500, dtype=np.float32)
    assert detect_crest_factor_anomaly(samples) is True


def test_detect_crest_factor_anomaly_true_for_isolated_impulse() -> None:
    # One loud spike in near-silence -- the "too high" case (one sparse
    # layer dominating over silence rather than an actual blended mix).
    samples = np.zeros(44100, dtype=np.float32)
    samples[100] = 1.0
    assert detect_crest_factor_anomaly(samples) is True


def test_detect_low_frequency_buildup_true_for_low_tone() -> None:
    samples = _sine(60, 2, 44100, 0.5)
    assert detect_low_frequency_buildup(samples, 44100) is True


def test_detect_low_frequency_buildup_false_for_mid_tone() -> None:
    samples = _sine(1000, 2, 44100, 0.5)
    assert detect_low_frequency_buildup(samples, 44100) is False


def test_check_combination_harmony_passes_for_a_clean_combination() -> None:
    samples = _sine(432, 3, 44100, 0.3)
    report = check_combination_harmony(
        samples, 44100, tone_frequency_hz=432.0, melody_root_note_hz=None
    )

    assert report.passed
    assert "crest_factor_db" in report.metrics
    assert "low_frequency_energy_ratio" in report.metrics


def test_check_combination_harmony_flags_beating_tone_and_melody() -> None:
    tone_hz = 440.0
    melody_hz = 440.0 * 2.0 ** (100.0 / 1200.0)
    samples = _sine(tone_hz, 3, 44100, 0.3)

    report = check_combination_harmony(
        samples, 44100, tone_frequency_hz=tone_hz, melody_root_note_hz=melody_hz
    )

    assert not report.passed
    assert any("beat" in issue for issue in report.issues)
    assert "tone_melody_interval_cents_from_consonance" in report.metrics
