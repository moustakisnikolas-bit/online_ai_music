import math
import random
from collections.abc import Iterable


def clamp(value: float, minimum: float = -1.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def apply_fades(
    samples: list[float],
    sample_rate: int,
    fade_in_seconds: float,
    fade_out_seconds: float,
) -> list[float]:
    total = len(samples)
    fade_in_frames = min(total, max(0, int(fade_in_seconds * sample_rate)))
    fade_out_frames = min(total, max(0, int(fade_out_seconds * sample_rate)))

    result = samples[:]

    if fade_in_frames > 0:
        for index in range(fade_in_frames):
            gain = index / fade_in_frames
            result[index] *= gain

    if fade_out_frames > 0:
        start = total - fade_out_frames
        for index in range(fade_out_frames):
            gain = 1.0 - (index / fade_out_frames)
            result[start + index] *= gain

    return result


def normalize(samples: Iterable[float], peak: float = 0.95) -> list[float]:
    values = list(samples)
    maximum = max((abs(value) for value in values), default=0.0)

    if maximum == 0:
        return values

    scale = peak / maximum
    return [clamp(value * scale) for value in values]


def generate_sine_samples(
    frequency_hz: float,
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
) -> list[float]:
    frame_count = duration_seconds * sample_rate
    angular = 2.0 * math.pi * frequency_hz

    return [
        amplitude * math.sin(angular * (index / sample_rate))
        for index in range(frame_count)
    ]


def generate_layered_tones(
    layers: list[tuple[float, float]],
    duration_seconds: int,
    sample_rate: int,
) -> list[float]:
    frame_count = duration_seconds * sample_rate
    samples = [0.0] * frame_count

    for frequency_hz, amplitude in layers:
        angular = 2.0 * math.pi * frequency_hz
        for index in range(frame_count):
            samples[index] += amplitude * math.sin(angular * (index / sample_rate))

    return normalize(samples)


def generate_white_noise(
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
    seed: int | None,
) -> list[float]:
    generator = random.Random(seed)
    frame_count = duration_seconds * sample_rate

    return [
        generator.uniform(-amplitude, amplitude)
        for _ in range(frame_count)
    ]


def generate_brown_noise(
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
    seed: int | None,
) -> list[float]:
    generator = random.Random(seed)
    frame_count = duration_seconds * sample_rate
    value = 0.0
    samples: list[float] = []

    for _ in range(frame_count):
        value += generator.uniform(-0.02, 0.02)
        value = clamp(value)
        samples.append(value)

    return normalize(samples, peak=amplitude)


def generate_pink_noise(
    duration_seconds: int,
    sample_rate: int,
    amplitude: float,
    seed: int | None,
) -> list[float]:
    generator = random.Random(seed)
    frame_count = duration_seconds * sample_rate

    b0 = b1 = b2 = b3 = b4 = b5 = b6 = 0.0
    samples: list[float] = []

    for _ in range(frame_count):
        white = generator.uniform(-1.0, 1.0)
        b0 = 0.99886 * b0 + white * 0.0555179
        b1 = 0.99332 * b1 + white * 0.0750759
        b2 = 0.96900 * b2 + white * 0.1538520
        b3 = 0.86650 * b3 + white * 0.3104856
        b4 = 0.55000 * b4 + white * 0.5329522
        b5 = -0.7616 * b5 - white * 0.0168980
        pink = b0 + b1 + b2 + b3 + b4 + b5 + b6 + white * 0.5362
        b6 = white * 0.115926
        samples.append(pink)

    return normalize(samples, peak=amplitude)
