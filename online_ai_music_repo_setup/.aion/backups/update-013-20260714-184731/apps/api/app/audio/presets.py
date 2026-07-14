from dataclasses import dataclass


@dataclass(frozen=True)
class ToneLayer:
    frequency_hz: float
    amplitude: float


@dataclass(frozen=True)
class AudioPreset:
    name: str
    mode: str
    layers: tuple[ToneLayer, ...] = ()
    noise_amplitude: float = 0.0


PRESETS: dict[str, AudioPreset] = {
    "calm-432": AudioPreset(
        name="calm-432",
        mode="layered_tones",
        layers=(
            ToneLayer(frequency_hz=432.0, amplitude=0.16),
            ToneLayer(frequency_hz=216.0, amplitude=0.08),
        ),
    ),
    "focus-alpha-bed": AudioPreset(
        name="focus-alpha-bed",
        mode="layered_tones",
        layers=(
            ToneLayer(frequency_hz=220.0, amplitude=0.12),
            ToneLayer(frequency_hz=230.0, amplitude=0.12),
        ),
    ),
    "deep-brown": AudioPreset(
        name="deep-brown",
        mode="brown_noise",
        noise_amplitude=0.22,
    ),
    "soft-pink": AudioPreset(
        name="soft-pink",
        mode="pink_noise",
        noise_amplitude=0.18,
    ),
}


def get_preset(name: str) -> AudioPreset:
    try:
        return PRESETS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown audio preset: {name}") from exc
