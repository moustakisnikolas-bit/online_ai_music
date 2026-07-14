from pydantic import BaseModel


class PresetLayerResponse(BaseModel):
    frequency_hz: float
    amplitude: float


class PresetResponse(BaseModel):
    name: str
    label: str
    description: str
    mode: str
    recommended_duration_seconds: int
    layers: list[PresetLayerResponse]
    noise_amplitude: float
