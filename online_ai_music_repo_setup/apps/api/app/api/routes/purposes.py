from fastapi import APIRouter, HTTPException, status

from app.audio.purposes import get_purpose, list_purposes
from app.schemas.purpose import PurposeProfileResponse

router = APIRouter(prefix="/audio/purposes", tags=["audio-purposes"])


@router.get("", response_model=list[PurposeProfileResponse])
def list_audio_purposes() -> list[dict]:
    return list_purposes()


@router.get("/{purpose_id}", response_model=PurposeProfileResponse)
def get_audio_purpose(purpose_id: str) -> dict:
    try:
        profile = get_purpose(purpose_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return {
        "id": profile.id,
        "label": profile.label,
        "description": profile.description,
        "recommended_duration_seconds": profile.recommended_duration_seconds,
        "target_lufs": profile.target_lufs,
        "true_peak_dbtp": profile.true_peak_dbtp,
        "energy_start": profile.energy_start,
        "energy_middle": profile.energy_middle,
        "energy_end": profile.energy_end,
        "suggested_mode": profile.suggested_mode,
        "notes": profile.notes,
    }
