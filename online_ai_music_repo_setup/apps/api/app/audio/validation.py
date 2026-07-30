from dataclasses import dataclass, field

import numpy as np


def detect_clipping(samples: np.ndarray, threshold: float = 0.999) -> bool:
    return bool(np.any(np.abs(samples) >= threshold))


def _max_true_run_length(mask: np.ndarray) -> int:
    if mask.size == 0:
        return 0

    padded = np.concatenate(([False], mask, [False]))
    diff = np.diff(padded.astype(np.int8))
    starts = np.flatnonzero(diff == 1)
    ends = np.flatnonzero(diff == -1)

    if starts.size == 0:
        return 0

    return int(np.max(ends - starts))


def detect_long_silence(
    samples: np.ndarray,
    sample_rate: int,
    silence_threshold: float = 0.001,
    min_silence_seconds: float = 5.0,
) -> bool:
    is_silent = np.abs(samples) < silence_threshold
    max_run = _max_true_run_length(is_silent)
    return max_run >= int(min_silence_seconds * sample_rate)


def detect_sudden_loudness_jumps(
    samples: np.ndarray,
    sample_rate: int,
    window_seconds: float = 0.4,
    threshold_db: float = 6.0,
) -> bool:
    window_frames = max(1, int(window_seconds * sample_rate))
    frame_count = len(samples) // window_frames

    if frame_count < 2:
        return False

    trimmed = samples[: frame_count * window_frames]
    windows = trimmed.reshape(frame_count, window_frames)
    rms = np.sqrt(np.mean(windows.astype(np.float64) ** 2, axis=1))
    rms = np.maximum(rms, 1e-9)
    db = 20.0 * np.log10(rms)
    deltas = np.abs(np.diff(db))

    return bool(np.any(deltas > threshold_db))


def detect_excessive_high_frequency_energy(
    samples: np.ndarray,
    sample_rate: int,
    cutoff_hz: float = 10000.0,
    ratio_threshold: float = 0.35,
) -> bool:
    if samples.size == 0:
        return False

    spectrum = np.abs(np.fft.rfft(samples.astype(np.float64)))
    freqs = np.fft.rfftfreq(len(samples), d=1.0 / sample_rate)
    total_energy = float(np.sum(spectrum**2))

    if total_energy <= 0:
        return False

    high_energy = float(np.sum(spectrum[freqs >= cutoff_hz] ** 2))
    return (high_energy / total_energy) > ratio_threshold


def detect_loop_seam_discontinuity(samples: np.ndarray, threshold: float = 0.15) -> bool:
    if samples.size < 2:
        return False

    return bool(abs(float(samples[0]) - float(samples[-1])) > threshold)


# Album-pipeline "harmony" checks: not a music-theory/chord analyzer (there
# isn't one for drone/noise/tone content), just spectral-collision and
# dynamic-range sanity checks -- the failure modes that actually matter for
# this content type. Plain numpy/scipy, consistent with the rest of this
# module.

# Equal-tempered consonant intervals within one octave, in cents from
# unison: unison/octave (0), major third, perfect fourth, perfect fifth,
# major sixth. A minor third is deliberately omitted -- close enough to a
# major third (300 vs 400 cents) that including both collapses the "near
# miss" detection zone between them to almost nothing.
_CONSONANT_INTERVALS_CENTS = (0.0, 400.0, 500.0, 700.0, 900.0)


def _cents_from_nearest_consonant_interval(tone_frequency_hz: float, melody_root_note_hz: float) -> float:
    ratio = tone_frequency_hz / melody_root_note_hz
    cents_from_unison = (1200.0 * np.log2(ratio)) % 1200.0

    return min(
        min(abs(cents_from_unison - point), 1200.0 - abs(cents_from_unison - point))
        for point in _CONSONANT_INTERVALS_CENTS
    )


def detect_tone_melody_beating(
    tone_frequency_hz: float,
    melody_root_note_hz: float | None,
    *,
    in_tune_tolerance_cents: float = 8.0,
    beat_zone_cents: float = 150.0,
) -> bool:
    # Flags the tone and melody sitting in the "near miss" zone -- close to
    # a consonant interval but detuned enough to produce audible beating/
    # roughness, rather than either a clean consonant interval (not
    # flagged) or a stable-if-dissonant one further away (a different,
    # harder-to-define problem this check isn't trying to catch).
    if melody_root_note_hz is None or tone_frequency_hz <= 0 or melody_root_note_hz <= 0:
        return False

    distance = _cents_from_nearest_consonant_interval(tone_frequency_hz, melody_root_note_hz)
    return bool(in_tune_tolerance_cents < distance <= beat_zone_cents)


def _crest_factor_db(samples: np.ndarray) -> float:
    if samples.size == 0:
        return 0.0

    peak = float(np.max(np.abs(samples)))
    if peak <= 0:
        return 0.0

    rms = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))
    if rms <= 0:
        return float("inf")

    return float(20.0 * np.log10(peak / rms))


def detect_crest_factor_anomaly(
    samples: np.ndarray,
    *,
    min_crest_db: float = 3.0,
    max_crest_db: float = 20.0,
) -> bool:
    # Too low suggests multiple full-level layers stacking without
    # headroom (an over-compressed clash); too high suggests one sparse
    # layer (typically a natural-sound sample with rare loud events)
    # dominating over near-silence rather than an actually blended mix.
    crest_db = _crest_factor_db(samples)
    return bool(crest_db < min_crest_db or crest_db > max_crest_db)


def _low_frequency_energy_ratio(samples: np.ndarray, sample_rate: int, cutoff_hz: float) -> float:
    if samples.size == 0:
        return 0.0

    spectrum = np.abs(np.fft.rfft(samples.astype(np.float64)))
    freqs = np.fft.rfftfreq(len(samples), d=1.0 / sample_rate)
    total_energy = float(np.sum(spectrum**2))

    if total_energy <= 0:
        return 0.0

    low_energy = float(np.sum(spectrum[freqs <= cutoff_hz] ** 2))
    return low_energy / total_energy


def detect_low_frequency_buildup(
    samples: np.ndarray,
    sample_rate: int,
    cutoff_hz: float = 150.0,
    ratio_threshold: float = 0.6,
) -> bool:
    # Catches brown noise stacking with a bass-heavy natural sound (ocean,
    # thunder, deep waterfall) into undifferentiated low-end mud --
    # detect_excessive_high_frequency_energy already covers the opposite
    # end, nothing today covers this one.
    return bool(_low_frequency_energy_ratio(samples, sample_rate, cutoff_hz) > ratio_threshold)


@dataclass(frozen=True)
class HarmonyCheckReport:
    issues: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return not self.issues


def check_combination_harmony(
    samples: np.ndarray,
    sample_rate: int,
    *,
    tone_frequency_hz: float,
    melody_root_note_hz: float | None,
) -> HarmonyCheckReport:
    # Run on a short preview render of a candidate album-track combination
    # (see services/album_combinations.py), never the full 1-hour render --
    # a failing combination should cost a cheap preview, not an hour of
    # wasted generation.
    base_report = validate_audio(samples, sample_rate)
    issues = list(base_report.issues)

    metrics: dict[str, float] = {
        "crest_factor_db": _crest_factor_db(samples),
        "low_frequency_energy_ratio": _low_frequency_energy_ratio(samples, sample_rate, 150.0),
    }

    if melody_root_note_hz is not None:
        metrics["tone_melody_interval_cents_from_consonance"] = _cents_from_nearest_consonant_interval(
            tone_frequency_hz, melody_root_note_hz
        )

    if detect_tone_melody_beating(tone_frequency_hz, melody_root_note_hz):
        issues.append("tone and melody root note are close enough to beat/clash")

    if detect_crest_factor_anomaly(samples):
        issues.append("crest factor outside the expected ambient-mix range")

    if detect_low_frequency_buildup(samples, sample_rate):
        issues.append("excessive low-frequency energy buildup detected")

    return HarmonyCheckReport(issues=issues, metrics=metrics)


@dataclass(frozen=True)
class ValidationReport:
    issues: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.issues


def validate_audio(
    samples: np.ndarray,
    sample_rate: int,
    *,
    check_loop_seam: bool = False,
) -> ValidationReport:
    # Advisory QA, not an auto-reject/regenerate gate: reports issues so a
    # reviewer sees them before approving, per the production spec's
    # "Required validation rules." Actually re-generating on failure is a
    # further step, deliberately not built here.
    issues = []

    if detect_clipping(samples):
        issues.append("clipping detected")

    if detect_long_silence(samples, sample_rate):
        issues.append("long digital silence detected")

    if detect_sudden_loudness_jumps(samples, sample_rate):
        issues.append("sudden loudness jump detected")

    if detect_excessive_high_frequency_energy(samples, sample_rate):
        issues.append("excessive high-frequency energy detected")

    if check_loop_seam and detect_loop_seam_discontinuity(samples):
        issues.append("audible loop boundary discontinuity detected")

    return ValidationReport(issues=issues)
