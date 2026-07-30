import numpy as np
import pyloudnorm as pyln
from scipy.signal import butter, fftconvolve, lfilter, resample_poly, sosfilt


def measure_lufs(samples: np.ndarray, sample_rate: int) -> float:
    # Integrated loudness per ITU-R BS.1770-4, via pyloudnorm rather than a
    # hand-rolled K-weighting + gating implementation -- loudness
    # compliance is the entire point of this feature, so using the
    # established reference implementation matters more than avoiding a
    # dependency. Returns -inf for silence/near-silence (pyloudnorm's own
    # convention); callers must check np.isfinite before using the result.
    meter = pyln.Meter(sample_rate)
    return float(meter.integrated_loudness(samples.astype(np.float64)))


def true_peak_dbtp(samples: np.ndarray, oversample: int = 4) -> float:
    # Oversampling before peak detection catches inter-sample peaks a
    # naive sample-peak check would miss (the "true" in true peak).
    if samples.size == 0:
        return float("-inf")

    oversampled = resample_poly(samples, oversample, 1)
    peak = float(np.max(np.abs(oversampled)))

    if peak <= 0:
        return float("-inf")

    return 20.0 * np.log10(peak)


def limit_true_peak(samples: np.ndarray, target_dbtp: float = -1.0) -> np.ndarray:
    # A single global gain reduction so the estimated true peak doesn't
    # exceed target_dbtp -- a mastering-pass limiter (uniform gain), not
    # an adaptive attack/release compressor.
    current = true_peak_dbtp(samples)

    if not np.isfinite(current) or current <= target_dbtp:
        return samples.astype(np.float32, copy=False)

    gain_linear = 10.0 ** ((target_dbtp - current) / 20.0)
    return (samples * gain_linear).astype(np.float32)


def normalize_to_lufs(
    samples: np.ndarray,
    sample_rate: int,
    target_lufs: float,
) -> np.ndarray:
    current = measure_lufs(samples, sample_rate)

    if not np.isfinite(current):
        return samples.astype(np.float32, copy=False)

    gain_linear = 10.0 ** ((target_lufs - current) / 20.0)
    return (samples * gain_linear).astype(np.float32)


def _peaking_eq(
    samples: np.ndarray,
    sample_rate: int,
    freq_hz: float,
    gain_db: float,
    q: float,
) -> np.ndarray:
    # RBJ Audio EQ Cookbook peaking-EQ biquad. scipy has no built-in
    # variable-gain peaking filter (iirpeak/iirnotch are fixed-depth
    # notches), so this is the standard closed-form derivation.
    nyquist = sample_rate / 2.0

    if freq_hz >= nyquist * 0.95:
        return samples

    a_coeff = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * np.pi * freq_hz / sample_rate
    alpha = np.sin(w0) / (2.0 * q)
    cos_w0 = np.cos(w0)

    b0 = 1.0 + alpha * a_coeff
    b1 = -2.0 * cos_w0
    b2 = 1.0 - alpha * a_coeff
    a0 = 1.0 + alpha / a_coeff
    a1 = -2.0 * cos_w0
    a2 = 1.0 - alpha / a_coeff

    b = np.array([b0, b1, b2]) / a0
    a = np.array([1.0, a1 / a0, a2 / a0])

    return lfilter(b, a, samples).astype(np.float32)


def apply_mastering_eq(samples: np.ndarray, sample_rate: int) -> np.ndarray:
    # Sub-bass control below ~32Hz, a gentle cut around 3.5kHz to keep the
    # 2-5kHz range smooth, and a gentle cut around 8kHz to avoid piercing
    # high-frequency energy -- directly from the production spec's
    # frequency-balance guidance, not arbitrary values.
    nyquist = sample_rate / 2.0
    hp_cutoff = min(32.0 / nyquist, 0.99)
    sos_hp = butter(2, hp_cutoff, btype="highpass", output="sos")
    shaped = sosfilt(sos_hp, samples).astype(np.float32)

    shaped = _peaking_eq(shaped, sample_rate, freq_hz=3500.0, gain_db=-2.0, q=1.0)
    shaped = _peaking_eq(shaped, sample_rate, freq_hz=8000.0, gain_db=-3.0, q=0.7)

    return shaped


def _synthesize_reverb_impulse(
    sample_rate: int,
    decay_seconds: float,
    seed: int,
) -> np.ndarray:
    # A synthesized room impulse response: exponentially-decaying noise,
    # lowpass-damped (real rooms absorb high frequencies faster than low
    # ones -- undamped white noise decaying by itself sounds like static,
    # not a room tail). This stands in for a literal Freeverb/Schroeder
    # comb-filter network, which doesn't vectorize the way the rest of
    # this module's DSP does (its per-sample feedback+lowpass loop can't
    # be batched through lfilter the way a plain filter can). Convolving
    # with this impulse response via FFT (see apply_reverb) is O(N log N)
    # and fully vectorized instead.
    length = max(1, int(decay_seconds * sample_rate))
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(length).astype(np.float32)

    t = np.arange(length, dtype=np.float32) / sample_rate
    # -60dB (1/1000) by decay_seconds, i.e. an RT60-style decay curve.
    envelope = np.exp(-t * (6.907755 / decay_seconds))
    impulse = noise * envelope

    nyquist = sample_rate / 2.0
    sos = butter(2, min(6000.0 / nyquist, 0.99), btype="lowpass", output="sos")
    impulse = sosfilt(sos, impulse).astype(np.float32)

    peak = float(np.max(np.abs(impulse)))
    return impulse / peak if peak > 0 else impulse


def apply_reverb(
    samples: np.ndarray,
    sample_rate: int,
    *,
    decay_seconds: float = 2.5,
    wet_level: float = 0.25,
    seed: int = 42,
) -> np.ndarray:
    if wet_level <= 0 or samples.size == 0:
        return samples.astype(np.float32, copy=False)

    impulse = _synthesize_reverb_impulse(sample_rate, decay_seconds, seed)
    wet = fftconvolve(samples, impulse, mode="full")[: len(samples)].astype(np.float32)

    # Rough level-match so wet_level is a meaningful dry/wet mix ratio
    # rather than being at the mercy of the impulse's own arbitrary scale.
    peak_in = float(np.max(np.abs(samples)))
    peak_wet = float(np.max(np.abs(wet)))
    if peak_wet > 0 and peak_in > 0:
        wet = wet * (peak_in / peak_wet)

    return ((1.0 - wet_level) * samples + wet_level * wet).astype(np.float32)


def fold_bass_to_mono(
    left: np.ndarray,
    right: np.ndarray,
    sample_rate: int,
    cutoff_hz: float = 120.0,
) -> tuple[np.ndarray, np.ndarray]:
    # Standard mastering technique: sum low-frequency content to mono
    # (avoids phase-cancellation artifacts on mono playback) while leaving
    # higher frequencies stereo. 4th-order (~24dB/octave) rather than 2nd
    # for a steeper crossover -- a gentler slope leaves too much bass
    # energy leaking into the "high" (still-stereo) band near the cutoff.
    nyquist = sample_rate / 2.0
    cutoff = min(cutoff_hz / nyquist, 0.99)
    sos_lp = butter(4, cutoff, btype="lowpass", output="sos")
    sos_hp = butter(4, cutoff, btype="highpass", output="sos")

    left_low = sosfilt(sos_lp, left)
    right_low = sosfilt(sos_lp, right)
    left_high = sosfilt(sos_hp, left)
    right_high = sosfilt(sos_hp, right)

    mono_low = (left_low + right_low) / 2.0

    new_left = (mono_low + left_high).astype(np.float32)
    new_right = (mono_low + right_high).astype(np.float32)

    return new_left, new_right
