from fastapi import APIRouter, HTTPException, status

from app.schemas.visuals import (
    ArtworkGenerateRequest,
    ArtworkGenerateResponse,
    VideoManifestRequest,
    VideoManifestResponse,
)
from app.services.artwork_generator import PRESETS, generate_artwork
from app.services.video_package import create_video_manifest

router = APIRouter(prefix="/visuals", tags=["visuals"])


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
) -> ArtworkGenerateResponse:
    try:
        path = generate_artwork(
            title=payload.title,
            subtitle=payload.subtitle,
            preset_name=payload.preset_name,
            output_dir=__import__("pathlib").Path(
                "data/generated/artwork"
            ),
            seed=payload.seed,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    preset = PRESETS[payload.preset_name]

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
