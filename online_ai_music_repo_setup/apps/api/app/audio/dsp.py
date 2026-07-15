import wave
from collections.abc import Iterable
from pathlib import Path

import numpy as np
from scipy.signal import lfilter, resample


def clamp(value: float, minimum: float = -1.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def normalize(samples: np.ndarray, peak: float = 0.95) -> np.ndarray:
    if samples.size == 0:
        return samples.astype(np.float32, copy=False)

    maximum = float(np.max(np.abs(samples)))

    if maximum == 0:
        return samples.astype(np.float32, copy=False)

    scale = peak / maximum
    return np.clip(samples * scale, -1.0, 1.0).astype(np.float32, copy=False)


def apply_fades(
    samples: np.ndarray,
    sample_rate: int,
    fade_in_seconds: float,
    fade_out_seconds: float,
) -> np.ndarray:
    total = len(samples)
    fade_in_frames = min(total, max(0, int(fade_in_seconds * sample_rate)))
    fade_out_frames = min(total, max(0, int(fade_out_seconds * sample_rate)))
    result = samples.copy()

    if fade_in_frames > 0:
        result[:fade_in_frames] *= np.arange(fade_in_frames) / fade_in_frames

    if fade_out_frames > 0:
        ramp = 1.0 - (np.arange(fade_out_frames) / fade_out_frames)
        result[total - fade_out_frames :] *= ramp

    return result


def apply_loop_crossfade(
    samples: np.ndarray,
    sample_rate: int,
    crossfade_seconds: float,
) -> np.ndarray:
    if crossfade_seconds <= 0:
        return samples

    crossfade_frames = min(
        len(samples) // 2,
        max(1, int(crossfade_seconds * sample_rate)),
    )

    if crossfade_frames <= 0:
        return samples

    result = samples.copy()
    ratio = np.arange(crossfade_frames) / crossfade_frames
    start_values = result[:crossfade_frames]
    end_values = result[len(result) - crossfade_frames :]
    blended = (start_values * ratio) + (end_values * (1.0 - ratio))
    result[:crossfade_frames] = blended
    result[len(result) - crossfade_frames :] = blended

    return result


def _time_axis(duration_seconds: int, sample_rate: int) -> np.ndarray:
    frame_count = duration_seconds * sample_rate
    return np.arange(frame_count, dtype=np.float32) / sample_rate


def generate_sine_samples(
    frequency_hz: float,
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
) -> np.ndarray:
    time_axis = _time_axis(duration_seconds, sample_rate)
    return amplitude * np.sin(2.0 * np.pi * frequency_hz * time_axis)


def generate_layered_tones(
    layers: list[tuple[float, float]],
    duration_seconds: int,
    sample_rate: int,
) -> np.ndarray:
    time_axis = _time_axis(duration_seconds, sample_rate)
    samples = np.zeros_like(time_axis)

    for frequency_hz, amplitude in layers:
        samples += amplitude * np.sin(2.0 * np.pi * frequency_hz * time_axis)

    return normalize(samples)


def generate_binaural_channels(
    left_frequency_hz: float,
    right_frequency_hz: float,
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
) -> tuple[np.ndarray, np.ndarray]:
    return (
        generate_sine_samples(
            left_frequency_hz,
            duration_seconds,
            sample_rate,
            amplitude,
        ),
        generate_sine_samples(
            right_frequency_hz,
            duration_seconds,
            sample_rate,
            amplitude,
        ),
    )


def generate_isochronic_samples(
    carrier_frequency_hz: float,
    pulse_frequency_hz: float,
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
    modulation_depth: float,
) -> np.ndarray:
    time_axis = _time_axis(duration_seconds, sample_rate)
    carrier = np.sin(2.0 * np.pi * carrier_frequency_hz * time_axis)
    modulation = 0.5 * (1.0 + np.sin(2.0 * np.pi * pulse_frequency_hz * time_axis))
    gain = (1.0 - modulation_depth) + (modulation_depth * modulation)
    return amplitude * gain * carrier


def generate_white_noise(
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
    seed: int | None,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    frame_count = duration_seconds * sample_rate
    return rng.uniform(-amplitude, amplitude, size=frame_count).astype(
        np.float32, copy=False
    )


def generate_brown_noise(
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
    seed: int | None,
) -> np.ndarray:
    # Brown/red noise is white noise integrated over time (a -6dB/octave
    # low-pass slope). A leaky integrator (single-pole IIR) implements this
    # in a numerically bounded, fully vectorizable way. The previous
    # implementation used a per-sample clamped random walk, which for long
    # durations spends most of its time pinned at the clamp boundary.
    rng = np.random.default_rng(seed)
    frame_count = duration_seconds * sample_rate
    white = rng.uniform(-1.0, 1.0, size=frame_count).astype(np.float32, copy=False)
    integrated = lfilter([0.02], [1.0, -0.999], white)
    return normalize(integrated, peak=amplitude)


def generate_pink_noise(
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
    seed: int | None,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    frame_count = duration_seconds * sample_rate
    white = rng.uniform(-1.0, 1.0, size=frame_count).astype(np.float32, copy=False)

    # Paul Kellet's refined pink noise filter: a cascade of one-pole
    # sections plus a one-sample-delayed term and a direct white term.
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

    delayed_white = np.concatenate(([0.0], white[:-1])).astype(
        np.float32, copy=False
    )
    pink += delayed_white * 0.115926
    pink += white * 0.5362

    return normalize(pink, peak=amplitude)


def generate_rain_texture(
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
    seed: int | None,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    frame_count = duration_seconds * sample_rate

    base = rng.uniform(-1.0, 1.0, size=frame_count).astype(np.float32, copy=False)
    base *= 0.35
    drop_hits = rng.random(frame_count) < 0.004
    drop_values = rng.uniform(0.4, 1.0, size=frame_count).astype(
        np.float32, copy=False
    )
    drops = np.where(drop_hits, drop_values, np.float32(0.0))

    samples = (base + drops) * amplitude
    return normalize(samples, peak=min(amplitude, 0.95))


def generate_wind_texture(
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
    seed: int | None,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    frame_count = duration_seconds * sample_rate
    time_axis = _time_axis(duration_seconds, sample_rate)

    white = rng.uniform(-1.0, 1.0, size=frame_count).astype(np.float32, copy=False)
    smooth = lfilter([0.005], [1.0, -0.995], white)
    swell = 0.55 + 0.45 * np.sin(2.0 * np.pi * 0.08 * time_axis)

    samples = smooth * swell * amplitude
    return normalize(samples, peak=min(amplitude, 0.95))


def load_sample_layer(
    sample_path: Path,
    duration_seconds: int,
    sample_rate: int,
) -> np.ndarray:
    # Loads a WAV file, downmixes to mono, resamples to the target sample
    # rate if needed, and loops (simple repeat-and-trim, not a crossfaded
    # seam) to fill the requested duration.
    with wave.open(str(sample_path), "rb") as wav_file:
        source_rate = wav_file.getframerate()
        channel_count = wav_file.getnchannels()
        frame_count = wav_file.getnframes()
        raw = wav_file.readframes(frame_count)

    pcm = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32767.0

    if pcm.size == 0:
        raise ValueError(f"Sample audio file has no frames: {sample_path}")

    if channel_count > 1:
        pcm = pcm.reshape(-1, channel_count).mean(axis=1)

    if source_rate != sample_rate:
        target_length = max(1, int(round(len(pcm) * sample_rate / source_rate)))
        pcm = resample(pcm, target_length).astype(np.float32)

    target_frames = duration_seconds * sample_rate
    tiles = int(np.ceil(target_frames / len(pcm)))
    return np.tile(pcm, tiles)[:target_frames]


def mix_tracks(
    tracks: Iterable[tuple[np.ndarray, float]],
    peak: float = 0.95,
) -> np.ndarray:
    # Consumes tracks one at a time and accumulates in place, rather than
    # requiring every layer's full-length array to be materialized and held
    # in memory simultaneously. For long, many-layer ambient mixes this is
    # the difference between O(1) and O(layer count) peak memory.
    mixed: np.ndarray | None = None
    frame_count: int | None = None

    for samples, gain in tracks:
        if frame_count is None:
            frame_count = len(samples)
            mixed = (samples * gain).astype(np.float32, copy=False)
        elif len(samples) != frame_count:
            raise ValueError("All mixed tracks must have equal frame counts")
        else:
            mixed += (samples * gain).astype(np.float32, copy=False)

    if mixed is None:
        return np.array([], dtype=np.float32)

    return normalize(mixed, peak=peak)
