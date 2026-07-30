from dataclasses import asdict

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.database import get_db
from app.audio.sample_library import (
    SAMPLE_LIBRARY_DIR,
    NaturalSoundSample,
    get_sample,
    list_samples,
    register_sample,
    resolve_sample_audio_path,
)
from app.core.config import get_settings
from app.repositories.generation_costs import STABLE_AUDIO_OPEN, record_estimated_cost
from app.schemas.instrumental import InstrumentalGenerationRequest
from app.schemas.sample import (
    FreesoundImportRequest,
    FreesoundSearchResultItem,
    NaturalSoundSampleResponse,
)
from app.services.freesound_importer import import_sample_from_freesound, search_cc0_sounds
from app.services.instrumental_generator import generate_instrumental_clip

router = APIRouter(prefix="/audio/samples", tags=["audio-samples"])


@router.get("", response_model=list[NaturalSoundSampleResponse])
def list_natural_sound_samples() -> list[NaturalSoundSampleResponse]:
    responses = []

    for entry in list_samples():
        sample = get_sample(entry["id"])

        try:
            resolve_sample_audio_path(sample, SAMPLE_LIBRARY_DIR)
            available = True
        except (ValueError, FileNotFoundError):
            available = False

        responses.append(NaturalSoundSampleResponse(**entry, available=available))

    return responses


@router.post("/generate", response_model=NaturalSoundSampleResponse)
def generate_instrumental_sample(
    payload: InstrumentalGenerationRequest,
    db: Session = Depends(get_db),
) -> NaturalSoundSampleResponse:
    filename = f"{payload.sample_id}.wav"
    output_path = SAMPLE_LIBRARY_DIR / filename

    try:
        generate_instrumental_clip(
            payload.prompt,
            duration_seconds=payload.duration_seconds,
            output_path=output_path,
            seed=payload.seed,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except (RuntimeError, TimeoutError, httpx.HTTPError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Instrumental generation failed: {exc}",
        ) from exc

    record_estimated_cost(
        db,
        kind=STABLE_AUDIO_OPEN,
        estimate_usd=get_settings().stable_audio_open_cost_usd,
        reference=payload.sample_id,
    )

    sample = NaturalSoundSample(
        id=payload.sample_id,
        label=payload.label,
        category=payload.category,
        filename=filename,
        license=(
            "Stable Audio Open (Stability AI Community License -- free for "
            "commercial use under $1M/yr annual revenue)"
        ),
        source_url=None,
        attribution=f"Generated via {get_settings().stable_audio_model}, prompt: {payload.prompt!r}",
        source_type="ai_generated",
    )

    try:
        register_sample(sample)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return NaturalSoundSampleResponse(**asdict(sample), available=True)


@router.get("/freesound/search", response_model=list[FreesoundSearchResultItem])
def search_freesound(
    query: str,
    page_size: int = 15,
    db: Session = Depends(get_db),
) -> list[FreesoundSearchResultItem]:
    try:
        return search_cc0_sounds(query, db=db, page_size=page_size)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Freesound search failed: {exc}",
        ) from exc


@router.post("/import-from-freesound", response_model=NaturalSoundSampleResponse)
def import_from_freesound(
    payload: FreesoundImportRequest,
    db: Session = Depends(get_db),
) -> NaturalSoundSampleResponse:
    try:
        sample = import_sample_from_freesound(
            payload.freesound_id,
            sample_id=payload.sample_id,
            label=payload.label,
            category=payload.category,
            db=db,
        )
    except ValueError as exc:
        # _ensure_configured raises for an unconfigured key; the license
        # re-check also raises ValueError for a non-CC0 sound -- but a
        # duplicate sample_id (register_sample) is the only one of these
        # that should map to 409 rather than 503/400.
        if "already exists" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
        if "not configured" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Freesound import failed: {exc}",
        ) from exc

    return NaturalSoundSampleResponse(**asdict(sample), available=True)
