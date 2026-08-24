import wave
from collections.abc import Iterable
from pathlib import Path

import numpy as np
from scipy.signal import lfilter, lfilter_zi, resample


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


def apply_energy_envelope(
    samples: np.ndarray,
    energy_start: float,
    energy_middle: float,
    energy_end: float,
) -> np.ndarray:
    # A macro amplitude arc over the whole track (start -> middle -> end),
    # implementing the production spec's "emotional journey" concept
    # honestly: this shapes overall loudness/intensity, not "harmonic
    # movement" or "melodic complexity" -- those don't exist without a
    # composition engine. Piecewise-linear between the three control
    # points rather than a spline, matching the spec's own "gradual
    # dynamic changes only" guidance -- linear interpolation can't
    # overshoot past the given values the way a spline could.
    frame_count = len(samples)

    if frame_count == 0:
        return samples

    control_positions = [0, max(0, frame_count // 2), max(0, frame_count - 1)]
    control_values = [energy_start, energy_middle, energy_end]
    envelope = np.interp(
        np.arange(frame_count), control_positions, control_values
    ).astype(np.float32)

    return (samples * envelope).astype(np.float32)


def apply_breathing_sync(
    samples: np.ndarray,
    sample_rate: int,
    inhale_seconds: float,
    exhale_seconds: float,
    depth: float,
) -> np.ndarray:
    # Periodic swells timed to a breathing cycle (spec section 5): rise
    # during inhale, gently resolve during exhale. Each phase uses a
    # raised-cosine shape (smooth S-curve, zero slope at both ends) rather
    # than a linear ramp, per the spec's "use automation rather than
    # obvious rhythmic pulses" guidance -- a linear ramp has a sharp
    # corner at the top and bottom of each cycle that reads as a pulse; a
    # raised cosine doesn't. depth controls how much the envelope actually
    # modulates volume (0 = no effect, 1 = swings fully to silence at the
    # bottom of each exhale).
    frame_count = len(samples)

    if frame_count == 0:
        return samples

    cycle_seconds = inhale_seconds + exhale_seconds

    if cycle_seconds <= 0:
        return samples

    time_axis = np.arange(frame_count) / sample_rate
    phase_in_cycle = np.mod(time_axis, cycle_seconds)

    rising = 0.5 - 0.5 * np.cos(np.pi * phase_in_cycle / inhale_seconds)
    falling = 0.5 + 0.5 * np.cos(
        np.pi * (phase_in_cycle - inhale_seconds) / exhale_seconds
    )
    envelope = np.where(phase_in_cycle < inhale_seconds, rising, falling)

    gain = ((1.0 - depth) + depth * envelope).astype(np.float32)

    return (samples * gain).astype(np.float32)


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


# Paul Kellet's refined pink noise filter sums 6 one-pole sections (each
# applied in parallel to the same white-noise input, not cascaded) plus a
# one-sample-delayed term and a direct white term. That parallel sum of
# rational transfer functions is itself a single rational transfer
# function: combine over a common denominator (the product of the 6 poles).
# Computed here via polynomial arithmetic rather than hand-transcribed,
# since these poles sit very close to the unit circle (up to 0.99886) --
# even small coefficient rounding compounds into real divergence over long
# renders, so this is derived at import time to keep full float64
# precision instead of risking that by copy-pasting rounded literals.
# Verified (see test_pink_noise.py) against the original 6-call-plus-FIR
# implementation on 200k white-noise samples: max abs difference ~1e-6,
# i.e. float32 rounding noise, not a real change in frequency response.
# One `lfilter` call this way is ~6x faster than the original 6 calls on a
# 1-hour render (20.5s -> 3.2s, measured).
def _combine_pink_noise_filter() -> tuple[np.ndarray, np.ndarray]:
    sections = (
        (0.99886, 0.0555179),
        (0.99332, 0.0750759),
        (0.96900, 0.1538520),
        (0.86650, 0.3104856),
        (0.55000, 0.5329522),
        (-0.7616, -0.0168980),
    )

    factors = [np.array([1.0, -pole]) for pole, _gain in sections]

    denominator = np.array([1.0])
    for factor in factors:
        denominator = np.convolve(denominator, factor)

    numerator = np.array([0.0])
    for i, (_pole, gain) in enumerate(sections):
        product = np.array([1.0])
        for j, factor in enumerate(factors):
            if j != i:
                product = np.convolve(product, factor)
        term = gain * product
        padded = np.zeros(max(len(numerator), len(term)))
        padded[: len(numerator)] += numerator
        padded[: len(term)] += term
        numerator = padded

    # Fold the FIR terms (delayed_white * 0.115926, direct white * 0.5362)
    # over the same common denominator: X(z) becomes X(z) * D(z) / D(z).
    delayed_term = np.concatenate(([0.0], 0.115926 * denominator))
    direct_term = 0.5362 * denominator

    total_len = max(len(numerator), len(delayed_term), len(direct_term))
    combined_numerator = np.zeros(total_len)
    for term in (numerator, delayed_term, direct_term):
        combined_numerator[: len(term)] += term

    return combined_numerator, denominator


_PINK_NOISE_NUMERATOR, _PINK_NOISE_DENOMINATOR = _combine_pink_noise_filter()


def generate_pink_noise(
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
    seed: int | None,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    frame_count = duration_seconds * sample_rate
    white = rng.uniform(-1.0, 1.0, size=frame_count).astype(np.float32, copy=False)

    pink = lfilter(_PINK_NOISE_NUMERATOR, _PINK_NOISE_DENOMINATOR, white)

    return normalize(pink, peak=amplitude)


def generate_violet_noise(
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
    seed: int | None,
) -> np.ndarray:
    # Violet/purple noise is white noise *differentiated* (a first-
    # difference FIR, the mirror image of brown noise's integration
    # below) -- +6dB/octave, the opposite slope of brown's -6dB/octave.
    rng = np.random.default_rng(seed)
    frame_count = duration_seconds * sample_rate
    white = rng.uniform(-1.0, 1.0, size=frame_count).astype(np.float32, copy=False)
    violet = lfilter([1.0, -1.0], [1.0], white)
    return normalize(violet, peak=amplitude)


def generate_blue_noise(
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
    seed: int | None,
) -> np.ndarray:
    # Blue/azure noise is pink noise differentiated: pink is already
    # -3dB/octave, and differentiation adds +6dB/octave on top of
    # whatever slope it's applied to, landing blue at +3dB/octave -- the
    # mirror image of pink, same relationship blue/violet already have.
    rng = np.random.default_rng(seed)
    frame_count = duration_seconds * sample_rate
    white = rng.uniform(-1.0, 1.0, size=frame_count).astype(np.float32, copy=False)
    pink = lfilter(_PINK_NOISE_NUMERATOR, _PINK_NOISE_DENOMINATOR, white)
    blue = lfilter([1.0, -1.0], [1.0], pink)
    return normalize(blue, peak=amplitude)


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
    tuning_hz: float = 440.0,
) -> np.ndarray:
    # Sparse, randomly-timed decaying tones at consonant (pentatonic)
    # pitches -- a genuine synthesized instrument sound rather than an
    # approximation of one, unlike birds_texture. tuning_hz is the only
    # place a concert-pitch reference matters in this engine: every other
    # mode takes a frequency_hz directly from the caller (there's no note
    # system to retune), but chimes has named pitches (C5/D5/E5/G5/A5)
    # defined relative to A440 by construction.
    rng = np.random.default_rng(seed)
    frame_count = duration_seconds * sample_rate
    samples = np.zeros(frame_count, dtype=np.float32)

    tuning_ratio = tuning_hz / 440.0
    pitches_hz = tuple(
        freq * tuning_ratio
        for freq in (523.25, 587.33, 659.25, 783.99, 880.00)  # C5 D5 E5 G5 A5
    )

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


def generate_deep_waterfall_texture(
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
    seed: int | None,
) -> np.ndarray:
    # A large waterfall's roar is dominated by low-frequency mass -- unlike
    # waves_texture's mid-weight wash or water_texture's bright babble --
    # with a thin layer of high-frequency mist/spray on top for scale
    # rather than character. Two bands combined, not one, and a much
    # slower/subtler depth movement than wind or waves' swell, since a
    # large falling body of water isn't perfectly static but doesn't
    # gust either.
    rng = np.random.default_rng(seed)
    frame_count = duration_seconds * sample_rate
    time_axis = _time_axis(duration_seconds, sample_rate)

    white_body = rng.uniform(-1.0, 1.0, size=frame_count).astype(np.float32, copy=False)
    body = lfilter([0.006], [1.0, -0.994], white_body)

    white_mist = rng.uniform(-1.0, 1.0, size=frame_count).astype(np.float32, copy=False)
    mist = lfilter([1.0, -1.0], [1.0, -0.6], white_mist).astype(np.float32) * 0.12

    depth = 0.9 + 0.1 * np.sin(2.0 * np.pi * 0.02 * time_axis)

    samples = (body + mist) * depth * amplitude
    return normalize(samples, peak=min(amplitude, 0.95))


def generate_distant_thunder_texture(
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
    seed: int | None,
) -> np.ndarray:
    # A softer, more heavily low-passed variant of thunder_texture: no
    # sharp crack, just a duller, quieter rumble as if reaching from far
    # away -- rarer triggers and a heavier low-pass on the boom itself
    # than thunder_texture's closer, punchier version.
    rng = np.random.default_rng(seed)
    frame_count = duration_seconds * sample_rate

    white = rng.uniform(-1.0, 1.0, size=frame_count).astype(np.float32, copy=False)
    rumble = lfilter([0.004], [1.0, -0.997], white).astype(np.float32)

    boom_hits = rng.random(frame_count) < 0.00003
    boom_noise = rng.uniform(-1.0, 1.0, size=frame_count).astype(np.float32, copy=False)
    triggers = np.where(boom_hits, boom_noise, np.float32(0.0))
    booms = lfilter([1.0], [1.0, -0.9997], triggers).astype(np.float32)
    booms = lfilter([0.008], [1.0, -0.99], booms).astype(np.float32)

    samples = (rumble * 0.6 + booms * 1.2) * amplitude
    return normalize(samples, peak=min(amplitude, 0.9))


def generate_airplane_cabin_texture(
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
    seed: int | None,
) -> np.ndarray:
    # Unlike every other texture in this module, a cabin's engine drone is
    # nearly constant -- no swell, no sparse events -- so this combines a
    # steady low-frequency hum (the engine's fundamental plus its first
    # harmonic) with broadband ventilation/wind hiss, rather than the
    # weather-driven amplitude movement every other texture here has.
    rng = np.random.default_rng(seed)
    frame_count = duration_seconds * sample_rate
    time_axis = _time_axis(duration_seconds, sample_rate)

    hum = (
        0.6 * np.sin(2.0 * np.pi * 100.0 * time_axis)
        + 0.4 * np.sin(2.0 * np.pi * 200.0 * time_axis)
    ).astype(np.float32)

    white = rng.uniform(-1.0, 1.0, size=frame_count).astype(np.float32, copy=False)
    hiss = lfilter([0.02], [1.0, -0.96], white).astype(np.float32)

    samples = (hum * 0.5 + hiss * 0.5) * amplitude
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


def _one_pole_lowpass(
    x: np.ndarray, tau_seconds: float, sample_rate: int, initial_value: float
) -> np.ndarray:
    # The exact discretization for a given real-time time constant (more
    # precise than hand-picking a coefficient the way the texture
    # generators above do for their noise beds, since here attack_seconds/
    # release_seconds are meant to mean something specific in real time).
    alpha = 1.0 - np.exp(-1.0 / (tau_seconds * sample_rate))
    b = [alpha]
    a = [1.0, -(1.0 - alpha)]
    # Seeded to a steady-state matching initial_value rather than zero --
    # an unseeded filter ramps up from 0 over the first tau_seconds
    # regardless of the actual input, which would either look like a
    # spurious event (for the envelope followers) or a spurious ducking
    # dip at time zero (for the gain-curve trackers below).
    zi = lfilter_zi(b, a) * initial_value
    y, _ = lfilter(b, a, x, zi=zi)
    return y


def compute_duck_envelope(
    samples: np.ndarray,
    sample_rate: int,
    duck_depth: float = 0.6,
    attack_seconds: float = 0.01,
    release_seconds: float = 0.35,
    slow_window_seconds: float = 0.5,
    threshold_ratio: float = 2.2,
) -> np.ndarray:
    """Detects transient events in `samples` (a short/fast envelope
    spiking well above a longer/slow "background level" envelope) and
    returns a per-sample gain multiplier -- 1.0 normally, dipping to
    (1 - duck_depth) during and briefly after each detected event, with a
    fast attack and a slower release -- meant to be multiplied onto
    *other* tracks in a mix so an event-driven texture (a thunder boom, a
    fire pop) cuts through the calmer layers around it, the same
    technique real audio engineers call sidechain ducking.

    Two one-pole low-passes at different time constants, taking the
    pointwise minimum, is the standard way to get asymmetric fast-attack/
    slow-release ballistics without a per-sample conditional loop: when
    the target steps down, the fast filter reaches it first; when it
    steps back up, the slow filter is still catching up from below.
    """
    if samples.size == 0:
        return np.array([], dtype=np.float32)

    rectified = np.abs(samples).astype(np.float64)
    peak = float(np.max(rectified))

    if peak <= 0.0:
        return np.ones(len(samples), dtype=np.float32)

    fast_env = _one_pole_lowpass(rectified, attack_seconds, sample_rate, rectified[0])
    slow_env = _one_pole_lowpass(rectified, slow_window_seconds, sample_rate, rectified[0])

    # The peak-scaled floor guards against spuriously triggering on
    # floating-point noise once slow_env is near zero (e.g. a near-silent
    # request), while still letting genuinely quiet requests trigger
    # normally -- an absolute floor would do neither correctly.
    trigger = (fast_env > slow_env * threshold_ratio) & (fast_env > 1e-3 * peak)
    target = np.where(trigger, 1.0 - duck_depth, 1.0)

    fast_track = _one_pole_lowpass(target, attack_seconds, sample_rate, 1.0)
    slow_track = _one_pole_lowpass(target, release_seconds, sample_rate, 1.0)

    return np.minimum(fast_track, slow_track).astype(np.float32)


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
