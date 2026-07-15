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


def generate_waves_texture(
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
    seed: int | None,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    frame_count = duration_seconds * sample_rate
    time_axis = _time_axis(duration_seconds, sample_rate)

    white = rng.uniform(-1.0, 1.0, size=frame_count).astype(np.float32, copy=False)
    # Heavier low-pass than wind_texture for a duller, rumbling wash rather
    # than a whooshing gust.
    wash = lfilter([0.01], [1.0, -0.995], white)

    # Two slow sines at incommensurate frequencies rather than one periodic
    # LFO, so wave sets swell in and out without sounding metronomic.
    swell = (
        0.5
        + 0.3 * np.sin(2.0 * np.pi * 0.045 * time_axis)
        + 0.2 * np.sin(2.0 * np.pi * 0.071 * time_axis + 1.3)
    )
    swell = np.clip(swell, 0.15, 1.0)

    samples = wash * swell * amplitude
    return normalize(samples, peak=min(amplitude, 0.95))


def generate_birds_texture(
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
    seed: int | None,
) -> np.ndarray:
    # Sparse, randomly-timed frequency-swept tone bursts approximating bird
    # calls. This is a rough synthesized approximation -- convincing
    # birdsong needs a real recording or an AI-generated clip (see
    # audio/sample_library.py and services/instrumental_generator.py),
    # not more DSP tone math.
    rng = np.random.default_rng(seed)
    frame_count = duration_seconds * sample_rate
    samples = np.zeros(frame_count, dtype=np.float32)

    position = 0
    while position < frame_count:
        position += int(rng.uniform(0.8, 3.5) * sample_rate)

        if position >= frame_count:
            break

        chirp_frames = max(1, int(rng.uniform(0.08, 0.22) * sample_rate))
        end = min(frame_count, position + chirp_frames)
        length = end - position

        if length <= 1:
            position = end
            continue

        start_freq = rng.uniform(2200, 4500)
        end_freq = start_freq + rng.uniform(-1200, 1800)
        instantaneous_freq = np.linspace(start_freq, end_freq, length)
        phase = 2.0 * np.pi * np.cumsum(instantaneous_freq) / sample_rate
        envelope = np.sin(np.pi * np.arange(length) / (length - 1)) ** 2
        chirp = (np.sin(phase) * envelope).astype(np.float32)

        samples[position:end] += chirp
        position = end

    return normalize(samples, peak=min(amplitude, 0.9))


def generate_fire_texture(
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
    seed: int | None,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    frame_count = duration_seconds * sample_rate

    white = rng.uniform(-1.0, 1.0, size=frame_count).astype(np.float32, copy=False)
    bed = lfilter([0.03], [1.0, -0.98], white).astype(np.float32) * 0.4

    # Sparse pop impulses shaped by a short exponential-decay filter --
    # an IIR filter's impulse response is naturally an exponential decay,
    # so this turns each random trigger into a short "pop" tail in one
    # vectorized pass instead of a per-event loop.
    pop_hits = rng.random(frame_count) < 0.0012
    pop_noise = rng.uniform(-1.0, 1.0, size=frame_count).astype(np.float32, copy=False)
    triggers = np.where(pop_hits, pop_noise, np.float32(0.0))
    crackle = lfilter([1.0], [1.0, -0.85], triggers).astype(np.float32)

    samples = (bed + crackle * 0.6) * amplitude
    return normalize(samples, peak=min(amplitude, 0.95))


def generate_water_texture(
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
    seed: int | None,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    frame_count = duration_seconds * sample_rate
    time_axis = _time_axis(duration_seconds, sample_rate)

    white = rng.uniform(-1.0, 1.0, size=frame_count).astype(np.float32, copy=False)
    # Lighter low-pass than wind/waves for a brighter, more constant babble.
    flow = lfilter([0.05], [1.0, -0.9], white)

    # Faster, gentler micro-modulation than wind's swell -- a near-constant
    # level with a subtle bubbling wobble instead of gusts rolling in.
    shimmer = 0.85 + 0.15 * np.sin(
        2.0 * np.pi * 0.6 * time_axis + float(rng.uniform(0, 2 * np.pi))
    )

    samples = flow * shimmer * amplitude
    return normalize(samples, peak=min(amplitude, 0.95))


def generate_thunder_texture(
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
    seed: int | None,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    frame_count = duration_seconds * sample_rate

    white = rng.uniform(-1.0, 1.0, size=frame_count).astype(np.float32, copy=False)
    rumble = lfilter([0.008], [1.0, -0.995], white).astype(np.float32)

    # Rare, low-frequency boom bursts: sparse triggers shaped by a slow
    # decay filter, then an extra low-pass so each boom reads as deep
    # rather than a sharp crack.
    boom_hits = rng.random(frame_count) < 0.00006
    boom_noise = rng.uniform(-1.0, 1.0, size=frame_count).astype(np.float32, copy=False)
    triggers = np.where(boom_hits, boom_noise, np.float32(0.0))
    booms = lfilter([1.0], [1.0, -0.9995], triggers).astype(np.float32)
    booms = lfilter([0.02], [1.0, -0.98], booms).astype(np.float32)

    samples = (rumble * 0.5 + booms * 1.5) * amplitude
    return normalize(samples, peak=min(amplitude, 0.95))


def generate_chimes_texture(
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
    seed: int | None,
) -> np.ndarray:
    # Sparse, randomly-timed decaying tones at consonant (pentatonic)
    # pitches -- a genuine synthesized instrument sound rather than an
    # approximation of one, unlike birds_texture.
    rng = np.random.default_rng(seed)
    frame_count = duration_seconds * sample_rate
    samples = np.zeros(frame_count, dtype=np.float32)

    pitches_hz = (523.25, 587.33, 659.25, 783.99, 880.00)  # C5 D5 E5 G5 A5

    position = 0
    while position < frame_count:
        position += int(rng.uniform(1.5, 5.0) * sample_rate)

        if position >= frame_count:
            break

        chime_frames = min(int(rng.uniform(1.2, 2.5) * sample_rate), frame_count - position)

        if chime_frames <= 1:
            continue

        frequency = float(rng.choice(pitches_hz)) * float(rng.choice((1.0, 2.0)))
        chime_time = np.arange(chime_frames) / sample_rate
        envelope = np.exp(-chime_time * 2.0)
        tone = (np.sin(2.0 * np.pi * frequency * chime_time) * envelope).astype(np.float32)

        end = position + chime_frames
        samples[position:end] += tone
        position = end

    return normalize(samples, peak=min(amplitude, 0.9))


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
        if mixed is None:
            frame_count = len(samples)
            mixed = (samples * gain).astype(np.float32, copy=False)
        elif len(samples) != frame_count:
            raise ValueError("All mixed tracks must have equal frame counts")
        else:
            mixed += (samples * gain).astype(np.float32, copy=False)

    if mixed is None:
        return np.array([], dtype=np.float32)

    return normalize(mixed, peak=peak)
