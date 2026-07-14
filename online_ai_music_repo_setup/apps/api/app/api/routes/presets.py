from fastapi import APIRouter, HTTPException, status

from app.audio.presets import get_preset, list_presets
from app.schemas.preset import PresetResponse

router = APIRouter(prefix="/audio/presets", tags=["audio-presets"])


@router.get("", response_model=list[PresetResponse])
def list_audio_presets() -> list[dict]:
    return list_presets()


@router.get("/{preset_name}", response_model=PresetResponse)
def get_audio_preset(preset_name: str) -> dict:
    try:
        preset = get_preset(preset_name)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return {
        "name": preset.name,
        "label": preset.label,
        "description": preset.description,
        "mode": preset.mode,
        "recommended_duration_seconds": preset.recommended_duration_seconds,
        "layers": [
            {
                "frequency_hz": layer.frequency_hz,
                "amplitude": layer.amplitude,
            }
            for layer in preset.layers
        ],
        "noise_amplitude": preset.noise_amplitude,
    }
