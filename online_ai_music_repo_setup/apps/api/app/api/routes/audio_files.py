from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.core.config import get_settings

router = APIRouter(prefix="/audio/files", tags=["audio-files"])

ALLOWED_SUFFIXES = {".wav", ".flac", ".mp3"}


def resolve_audio_file(filename: str) -> Path:
    if not filename or Path(filename).name != filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename.",
        )

    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported audio file type.",
        )

    settings = get_settings()
    base = settings.audio_output_path.resolve()
    path = (base / filename).resolve()

    if path.parent != base:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file path.",
        )

    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio file not found.",
        )

    return path


@router.get("/{filename}")
def download_audio_file(filename: str) -> FileResponse:
    path = resolve_audio_file(filename)

    media_types = {
        ".wav": "audio/wav",
        ".flac": "audio/flac",
        ".mp3": "audio/mpeg",
    }

    return FileResponse(
        path=path,
        media_type=media_types[path.suffix.lower()],
        filename=path.name,
    )
