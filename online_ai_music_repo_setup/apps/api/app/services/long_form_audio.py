from collections.abc import Callable
from pathlib import Path
import wave

import numpy as np
from scipy.signal import lfilter

ProgressCallback = Callable[[float], None]


def _measure_brown_noise_peak(seed: int, total_frames: int, chunk_frames: int) -> float:
    """Run the brown-noise leaky integrator once to find its true peak.

    The non-chunked path (dsp.generate_brown_noise) normalizes against the
    exact global peak of the whole signal, so "amplitude" means "the actual
    peak level" everywhere else in the app. True chunked/streaming rendering
    never holds the whole signal in memory, so that exact global peak can't
    be read off an array directly -- but the leaky integrator is cheap
    (lfilter processed 20M samples in well under a second in testing), so a
    first pass that only tracks a running scalar max (not the audio itself)
    reproduces the same peak-matching behavior for a small, mode-local
    compute cost instead of memory cost.
    """
    rng = np.random.default_rng(seed)
    filter_state = np.zeros(1)
    peak = 0.0
    frame_index = 0

    while frame_index < total_frames:
        current_chunk = min(chunk_frames, total_frames - frame_index)
        white = rng.uniform(-1.0, 1.0, size=current_chunk)
        integrated, filter_state = lfilter([0.02], [1.0, -0.999], white, zi=filter_state)
        chunk_peak = np.max(np.abs(integrated))
        if chunk_peak > peak:
            peak = float(chunk_peak)
        frame_index += current_chunk

    return peak


def _fade_gains(
    absolute_indices: np.ndarray,
    total_frames: int,
    sample_rate: int,
    fade_in_seconds: float,
    fade_out_seconds: float,
) -> np.ndarray:
    gains = np.ones(len(absolute_indices), dtype=np.float64)

    fade_in_frames = int(fade_in_seconds * sample_rate)
    fade_out_frames = int(fade_out_seconds * sample_rate)

    if fade_in_frames > 0:
        in_mask = absolute_indices < fade_in_frames
        gains[in_mask] *= absolute_indices[in_mask] / fade_in_frames

    if fade_out_frames > 0:
        out_mask = absolute_indices >= total_frames - fade_out_frames
        remaining = total_frames - absolute_indices[out_mask] - 1
        gains[out_mask] *= np.maximum(0.0, remaining / fade_out_frames)

    return gains


def render_long_form_wav(
    *,
    output_path: Path,
    mode: str,
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
    channels: int = 1,
    frequency_hz: float = 432.0,
    left_frequency_hz: float = 200.0,
    right_frequency_hz: float = 210.0,
    pulse_frequency_hz: float = 10.0,
    modulation_depth: float = 1.0,
    fade_in_seconds: float = 0.1,
    fade_out_seconds: float = 0.1,
    seed: int | None = None,
    chunk_frames: int = 65536,
    progress_callback: ProgressCallback | None = None,
) -> Path:
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")

    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")

    if channels not in {1, 2}:
        raise ValueError("channels must be 1 or 2")

    if chunk_frames <= 0:
        raise ValueError("chunk_frames must be positive")

    if mode == "binaural_beats" and channels != 2:
        raise ValueError("binaural_beats requires stereo output")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_frames = duration_seconds * sample_rate

    brown_noise_peak = 1.0
    if mode == "brown_noise":
        # Two passes need the same random stream, so a missing seed must be
        # pinned to a concrete value now rather than left to fresh OS entropy
        # on each `default_rng(None)` call (which would make the passes
        # diverge).
        effective_seed = seed if seed is not None else int(np.random.SeedSequence().entropy)
        brown_noise_peak = _measure_brown_noise_peak(effective_seed, total_frames, chunk_frames)
        seed = effective_seed

    rng = np.random.default_rng(seed)
    # scipy.signal.lfilter's zi/zf carry the brown-noise filter's internal
    # state across chunk boundaries, so the leaky integrator continues
    # seamlessly from one chunk into the next instead of resetting.
    brown_filter_state = np.zeros(1)

    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)

        frame_index = 0

        while frame_index < total_frames:
            current_chunk = min(chunk_frames, total_frames - frame_index)
            absolute_indices = np.arange(frame_index, frame_index + current_chunk)
            time_positions = absolute_indices / sample_rate
            gains = _fade_gains(
                absolute_indices,
                total_frames,
                sample_rate,
                fade_in_seconds,
                fade_out_seconds,
            )

            if mode == "sine":
                mono = amplitude * np.sin(2.0 * np.pi * frequency_hz * time_positions)
                channel_arrays = [mono] * channels

            elif mode == "isochronic_tones":
                carrier = np.sin(2.0 * np.pi * frequency_hz * time_positions)
                modulation = 0.5 * (
                    1.0 + np.sin(2.0 * np.pi * pulse_frequency_hz * time_positions)
                )
                modulated_gain = (1.0 - modulation_depth) + modulation_depth * modulation
                mono = amplitude * modulated_gain * carrier
                channel_arrays = [mono] * channels

            elif mode == "binaural_beats":
                left = amplitude * np.sin(2.0 * np.pi * left_frequency_hz * time_positions)
                right = amplitude * np.sin(2.0 * np.pi * right_frequency_hz * time_positions)
                channel_arrays = [left, right]

            elif mode == "white_noise":
                mono = rng.uniform(-amplitude, amplitude, size=current_chunk)
                channel_arrays = [mono] * channels

            elif mode == "brown_noise":
                white = rng.uniform(-1.0, 1.0, size=current_chunk)
                integrated, brown_filter_state = lfilter(
                    [0.02], [1.0, -0.999], white, zi=brown_filter_state
                )
                mono = (integrated / brown_noise_peak) * amplitude
                channel_arrays = [mono] * channels

            else:
                raise ValueError(f"Unsupported long-form mode: {mode}")

            stacked = np.stack([channel * gains for channel in channel_arrays], axis=1)
            pcm = (np.clip(stacked, -1.0, 1.0) * 32767).astype("<i2")
            wav_file.writeframesraw(pcm.tobytes())

            frame_index += current_chunk

            if progress_callback is not None:
                progress_callback(frame_index / total_frames)

        wav_file.writeframes(b"")

    return output_path
