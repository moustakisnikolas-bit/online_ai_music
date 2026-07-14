from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.schemas.visuals import (
    ExportBundleRequest,
    ExportBundleResponse,
    VideoRenderRequest,
    VideoRenderResponse,
)
from app.services.export_bundle import create_export_bundle
from app.services.video_renderer import render_static_video

router = APIRouter(prefix="/exports", tags=["exports"])

AUDIO_DIR = Path("data/generated/audio")
ARTWORK_DIR = Path("data/generated/artwork")
VIDEO_DIR = Path("data/generated/video")
EXPORT_DIR = Path("data/generated/exports")


@router.post(
    "/video/render",
    response_model=VideoRenderResponse,
)
def render_video(
    payload: VideoRenderRequest,
) -> VideoRenderResponse:
    try:
        path = render_static_video(
            audio_dir=AUDIO_DIR,
            artwork_dir=ARTWORK_DIR,
            output_dir=VIDEO_DIR,
            audio_filename=payload.audio_filename,
            artwork_filename=payload.artwork_filename,
            output_filename=payload.output_filename,
            width=payload.width,
            height=payload.height,
            frame_rate=payload.frame_rate,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Required media file not found: {exc}",
        ) from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return VideoRenderResponse(
        filename=path.name,
        file_path=str(path),
    )


@router.post(
    "/bundle",
    response_model=ExportBundleResponse,
)
def generate_export_bundle(
    payload: ExportBundleRequest,
) -> ExportBundleResponse:
    try:
        manifest_path, zip_path = create_export_bundle(
            title=payload.title,
            audio_dir=AUDIO_DIR,
            artwork_dir=ARTWORK_DIR,
            video_dir=VIDEO_DIR,
            export_dir=EXPORT_DIR,
            audio_filename=payload.audio_filename,
            artwork_filename=payload.artwork_filename,
            video_filename=payload.video_filename,
            metadata=payload.metadata,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Required package file not found: {exc}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return ExportBundleResponse(
        manifest_filename=manifest_path.name,
        manifest_path=str(manifest_path),
        zip_filename=zip_path.name,
        zip_path=str(zip_path),
    )


@router.get("/files/{filename}")
def download_export_file(filename: str) -> FileResponse:
    if not filename or Path(filename).name != filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename.",
        )

    if Path(filename).suffix.lower() not in {".zip", ".json", ".mp4"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported export file type.",
        )

    candidates = [
        (EXPORT_DIR / filename).resolve(),
        (VIDEO_DIR / filename).resolve(),
    ]

    for path in candidates:
        if path.exists() and path.is_file():
            media_type = {
                ".zip": "application/zip",
                ".json": "application/json",
                ".mp4": "video/mp4",
            }[path.suffix.lower()]

            return FileResponse(
                path=path,
                media_type=media_type,
                filename=path.name,
            )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Export file not found.",
    )
