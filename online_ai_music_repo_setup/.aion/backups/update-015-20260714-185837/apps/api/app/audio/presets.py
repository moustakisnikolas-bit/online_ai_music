from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ToneLayer:
    frequency_hz: float
    amplitude: float


@dataclass(frozen=True)
class AudioPreset:
    name: str
    label: str
    description: str
    mode: str
    recommended_duration_seconds: int
    layers: tuple[ToneLayer, ...] = ()
    noise_amplitude: float = 0.0


PRESETS: dict[str, AudioPreset] = {
    "calm-432": AudioPreset(
        name="calm-432",
        label="Calm 432",
        description="A soft layered tone bed centered on 432 Hz.",
        mode="layered_tones",
        recommended_duration_seconds=1800,
        layers=(
            ToneLayer(frequency_hz=432.0, amplitude=0.16),
            ToneLayer(frequency_hz=216.0, amplitude=0.08),
        ),
    ),
    "focus-alpha-bed": AudioPreset(
        name="focus-alpha-bed",
        label="Focus Alpha Bed",
        description="A gentle dual-tone bed for focus-oriented ambient listening.",
        mode="layered_tones",
        recommended_duration_seconds=1800,
        layers=(
            ToneLayer(frequency_hz=220.0, amplitude=0.12),
            ToneLayer(frequency_hz=230.0, amplitude=0.12),
        ),
    ),
    "deep-brown": AudioPreset(
        name="deep-brown",
        label="Deep Brown Noise",
        description="Low-frequency-weighted noise for a deep ambient background.",
        mode="brown_noise",
        recommended_duration_seconds=3600,
        noise_amplitude=0.22,
    ),
    "soft-pink": AudioPreset(
        name="soft-pink",
        label="Soft Pink Noise",
        description="Balanced pink noise with a softer high-frequency profile.",
        mode="pink_noise",
        recommended_duration_seconds=3600,
        noise_amplitude=0.18,
    ),
}


def get_preset(name: str) -> AudioPreset:
    try:
        return PRESETS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown audio preset: {name}") from exc


def list_presets() -> list[dict]:
    result: list[dict] = []

    for preset in PRESETS.values():
        payload = asdict(preset)
        payload["layers"] = [asdict(layer) for layer in preset.layers]
        result.append(payload)

    return sorted(result, key=lambda item: item["label"])
