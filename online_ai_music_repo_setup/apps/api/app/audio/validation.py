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
