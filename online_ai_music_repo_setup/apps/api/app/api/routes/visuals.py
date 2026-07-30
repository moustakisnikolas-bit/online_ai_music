from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.database import get_db
from app.core.config import get_settings
from app.repositories.generation_costs import (
    FLUX_REPLICATE,
    OPENROUTER_IMAGE,
    record_estimated_cost,
    record_reported_cost,
)
from app.schemas.visuals import (
    ArtworkGenerateRequest,
    ArtworkGenerateResponse,
    VideoManifestRequest,
    VideoManifestResponse,
)
from app.services.ai_artwork_generator import generate_ai_artwork
from app.services.artwork_generator import PRESETS, generate_artwork, safe_filename
from app.services.video_package import create_video_manifest

router = APIRouter(prefix="/visuals", tags=["visuals"])

_AI_ARTWORK_DIR = Path("data/generated/artwork")


def _default_style_prompt(title: str, subtitle: str) -> str:
    return (
        f"Photorealistic, high-detail album cover artwork for a therapeutic "
        f"ambient audio track titled '{title}' ({subtitle}). Calm, soothing, "
        f"cinematic lighting, no text or typography in the image."
    )


@router.get("/presets")
def list_visual_presets() -> list[dict]:
    return [
        {
            "name": name,
            "label": preset.label,
            "width": preset.width,
            "height": preset.height,
        }
        for name, preset in sorted(PRESETS.items())
    ]


@router.post(
    "/artwork/generate",
    response_model=ArtworkGenerateResponse,
)
def generate_visual_artwork(
    payload: ArtworkGenerateRequest,
    db: Session = Depends(get_db),
) -> ArtworkGenerateResponse:
    if payload.preset_name not in PRESETS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown artwork preset: {payload.preset_name}",
        )

    preset = PRESETS[payload.preset_name]

    if payload.provider == "procedural":
        try:
            path = generate_artwork(
                title=payload.title,
                subtitle=payload.subtitle,
                preset_name=payload.preset_name,
                output_dir=_AI_ARTWORK_DIR,
                seed=payload.seed,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
    else:
        prompt = payload.style_prompt or _default_style_prompt(
            payload.title, payload.subtitle
        )
        filename = f"{safe_filename(payload.title)}-{payload.preset_name}-{payload.seed}.png"
        try:
            result = generate_ai_artwork(
                prompt,
                output_path=_AI_ARTWORK_DIR / filename,
                provider=payload.provider,
                width=preset.width,
                height=preset.height,
                seed=payload.seed,
                db=db,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        except (RuntimeError, TimeoutError, httpx.HTTPError) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc

        path = result.path

        if payload.provider == "replicate":
            record_estimated_cost(
                db,
                kind=FLUX_REPLICATE,
                estimate_usd=get_settings().flux_replicate_cost_usd,
                reference=filename,
            )
        else:
            record_reported_cost(
                db, kind=OPENROUTER_IMAGE, reported_usd=result.cost_usd, reference=filename
            )

    return ArtworkGenerateResponse(
        filename=path.name,
        file_path=str(path),
        preset_name=payload.preset_name,
        width=preset.width,
        height=preset.height,
    )


@router.post(
    "/video/manifest",
    response_model=VideoManifestResponse,
)
def generate_video_manifest(
    payload: VideoManifestRequest,
) -> VideoManifestResponse:
    path = create_video_manifest(
        title=payload.title,
        audio_filename=payload.audio_filename,
        artwork_filename=payload.artwork_filename,
        duration_seconds=payload.duration_seconds,
        output_dir=__import__("pathlib").Path(
            "data/generated/video"
        ),
        width=payload.width,
        height=payload.height,
        frame_rate=payload.frame_rate,
    )

    return VideoManifestResponse(
        manifest_filename=path.name,
        manifest_path=str(path),
    )
