from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.schemas.visuals import (
    ExportBundleRequest,
    ExportBundleResponse,
    RenderedVideoResponse,
    VideoRenderRequest,
    VideoRenderResponse,
)
from app.services.export_bundle import create_export_bundle
from app.services.video_renderer import render_static_video

router = APIRouter(prefix="/exports", tags=["exports"])

# Not a hardcoded constant like the other dirs below: generated_audio_dir
# is a real Settings field (GENERATED_AUDIO_DIR), and this project's own
# .env overrides it to an absolute path outside the repo-relative
# "data/generated/audio" default -- audio_files.py (the actual audio
# serving route) already reads it this way. A hardcoded second constant
# here silently pointed at a different, empty directory than where audio
# is actually written, so every export/video-render request 404'd on a
# file that genuinely existed, just not where this route was looking.
def _audio_dir() -> Path:
    return get_settings().audio_output_path


ARTWORK_DIR = Path("data/generated/artwork")
VIDEO_DIR = Path("data/generated/video")
CAPTIONS_DIR = Path("data/generated/captions")
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
            audio_dir=_audio_dir(),
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
            audio_dir=_audio_dir(),
            artwork_dir=ARTWORK_DIR,
            video_dir=VIDEO_DIR,
            caption_dir=CAPTIONS_DIR,
            export_dir=EXPORT_DIR,
            audio_filename=payload.audio_filename,
            artwork_filename=payload.artwork_filename,
            video_filename=payload.video_filename,
            caption_filename=payload.caption_filename,
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


@router.get("/videos", response_model=list[RenderedVideoResponse])
def list_rendered_videos() -> list[RenderedVideoResponse]:
    if not VIDEO_DIR.exists():
        return []

    videos = []
    for path in sorted(VIDEO_DIR.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True):
        stat = path.stat()
        videos.append(
            RenderedVideoResponse(
                filename=path.name,
                size_bytes=stat.st_size,
                modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            )
        )

    return videos


@router.get("/files/{filename}")
def download_export_file(filename: str) -> FileResponse:
    if not filename or Path(filename).name != filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename.",
        )

    if Path(filename).suffix.lower() not in {".zip", ".json", ".mp4", ".srt"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported export file type.",
        )

    candidates = [
        (EXPORT_DIR / filename).resolve(),
        (VIDEO_DIR / filename).resolve(),
        (CAPTIONS_DIR / filename).resolve(),
    ]

    for path in candidates:
        if path.exists() and path.is_file():
            media_type = {
                ".zip": "application/zip",
                ".json": "application/json",
                ".mp4": "video/mp4",
                ".srt": "application/x-subrip",
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
