from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

router = APIRouter(prefix="/visuals/files", tags=["visual-files"])

ARTWORK_DIR = Path("data/generated/artwork")


@router.get("/{filename}")
def download_visual_file(filename: str) -> FileResponse:
    if not filename or Path(filename).name != filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename.",
        )

    if Path(filename).suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported visual file type.",
        )

    base = ARTWORK_DIR.resolve()
    path = (base / filename).resolve()

    if path.parent != base:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file path.",
        )

    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visual file not found.",
        )

    media_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }[path.suffix.lower()]

    return FileResponse(
        path=path,
        media_type=media_type,
        filename=path.name,
    )
