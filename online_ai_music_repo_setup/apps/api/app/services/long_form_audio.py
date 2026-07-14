import math
import random
import struct
import wave
from collections.abc import Callable
from pathlib import Path

ProgressCallback = Callable[[float], None]


def _clamp(value: float) -> float:
    return max(-1.0, min(1.0, value))


def _fade_gain(
    frame_index: int,
    total_frames: int,
    sample_rate: int,
    fade_in_seconds: float,
    fade_out_seconds: float,
) -> float:
    gain = 1.0

    fade_in_frames = int(fade_in_seconds * sample_rate)
    fade_out_frames = int(fade_out_seconds * sample_rate)

    if fade_in_frames > 0 and frame_index < fade_in_frames:
        gain *= frame_index / fade_in_frames

    if fade_out_frames > 0 and frame_index >= total_frames - fade_out_frames:
        remaining = total_frames - frame_index - 1
        gain *= max(0.0, remaining / fade_out_frames)

    return gain


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
    generator = random.Random(seed)
    brown_state = 0.0

    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)

        frame_index = 0

        while frame_index < total_frames:
            current_chunk = min(chunk_frames, total_frames - frame_index)
            frames = bytearray()

            for offset in range(current_chunk):
                absolute_index = frame_index + offset
                time_position = absolute_index / sample_rate
                gain = _fade_gain(
                    absolute_index,
                    total_frames,
                    sample_rate,
                    fade_in_seconds,
                    fade_out_seconds,
                )

                if mode == "sine":
                    value = amplitude * math.sin(
                        2.0 * math.pi * frequency_hz * time_position
                    )
                    channel_values = [value] * channels

                elif mode == "isochronic_tones":
                    carrier = math.sin(
                        2.0 * math.pi * frequency_hz * time_position
                    )
                    modulation = 0.5 * (
                        1.0
                        + math.sin(
                            2.0
                            * math.pi
                            * pulse_frequency_hz
                            * time_position
                        )
                    )
                    modulated_gain = (
                        (1.0 - modulation_depth)
                        + modulation_depth * modulation
                    )
                    value = amplitude * modulated_gain * carrier
                    channel_values = [value] * channels

                elif mode == "binaural_beats":
                    left = amplitude * math.sin(
                        2.0 * math.pi * left_frequency_hz * time_position
                    )
                    right = amplitude * math.sin(
                        2.0 * math.pi * right_frequency_hz * time_position
                    )
                    channel_values = [left, right]

                elif mode == "white_noise":
                    value = generator.uniform(-amplitude, amplitude)
                    channel_values = [value] * channels

                elif mode == "brown_noise":
                    brown_state += generator.uniform(-0.02, 0.02)
                    brown_state = _clamp(brown_state)
                    value = brown_state * amplitude
                    channel_values = [value] * channels

                else:
                    raise ValueError(f"Unsupported long-form mode: {mode}")

                for channel_value in channel_values:
                    pcm = int(_clamp(channel_value * gain) * 32767)
                    frames.extend(struct.pack("<h", pcm))

            wav_file.writeframesraw(bytes(frames))
            frame_index += current_chunk

            if progress_callback is not None:
                progress_callback(frame_index / total_frames)

        wav_file.writeframes(b"")

    return output_path
