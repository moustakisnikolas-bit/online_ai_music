from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.schemas.audio_asset import AudioAssetMetadataResponse
from app.services.audio_assets import inspect_wav, safe_asset_path

router = APIRouter(prefix="/audio/assets", tags=["audio-assets"])


def resolve_asset(filename: str) -> Path:
    settings = get_settings()

    try:
        path = safe_asset_path(settings.audio_output_path, filename)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio asset not found.",
        )

    return path


@router.get("/{filename}", response_model=AudioAssetMetadataResponse)
def get_audio_asset_metadata(
    filename: str,
    request: Request,
) -> AudioAssetMetadataResponse:
    path = resolve_asset(filename)

    try:
        metadata = inspect_wav(path)
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid WAV asset: {exc}",
        ) from exc

    download_url = str(
        request.url_for(
            "download_audio_asset",
            filename=filename,
        )
    )

    return AudioAssetMetadataResponse(
        filename=metadata.filename,
        file_size_bytes=metadata.file_size_bytes,
        checksum_sha256=metadata.checksum_sha256,
        channels=metadata.channels,
        sample_rate=metadata.sample_rate,
        sample_width_bytes=metadata.sample_width_bytes,
        frame_count=metadata.frame_count,
        duration_seconds=metadata.duration_seconds,
        download_url=download_url,
    )


@router.get("/{filename}/download", name="download_audio_asset")
def download_audio_asset(filename: str) -> FileResponse:
    path = resolve_asset(filename)

    return FileResponse(
        path=path,
        media_type="audio/wav",
        filename=path.name,
    )
