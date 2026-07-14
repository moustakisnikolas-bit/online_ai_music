#!/usr/bin/env bash
set -Eeuo pipefail

TARGET="${1:-/Users/nikolas/Documents/GitHub/online_ai_music/online_ai_music_repo_setup}"

if [[ ! -d "${TARGET}" ]]; then
  echo "ERROR: Target directory does not exist: ${TARGET}" >&2
  exit 1
fi

cd "${TARGET}"

BACKUP_DIR="${TARGET}/.aion/backups/update-018-$(date +%Y%m%d-%H%M%S)"
mkdir -p "${BACKUP_DIR}"

for file in \
  "apps/api/app/main.py" \
  "apps/api/app/schemas/visuals.py"; do
  if [[ -f "${file}" ]]; then
    mkdir -p "${BACKUP_DIR}/$(dirname "${file}")"
    cp "${file}" "${BACKUP_DIR}/${file}"
  fi
done

mkdir -p apps/api/app/services
mkdir -p apps/api/app/api/routes
mkdir -p apps/api/app/schemas
mkdir -p apps/api/tests
mkdir -p data/generated/exports
mkdir -p docs/07-integrations
mkdir -p docs/11-operations

cat > apps/api/app/services/video_renderer.py <<'EOF'
import shutil
import subprocess
from pathlib import Path


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _safe_file(base_dir: Path, filename: str, allowed_suffixes: set[str]) -> Path:
    if not filename or Path(filename).name != filename:
        raise ValueError("Invalid filename")

    suffix = Path(filename).suffix.lower()
    if suffix not in allowed_suffixes:
        raise ValueError(f"Unsupported file type: {suffix}")

    base = base_dir.resolve()
    path = (base / filename).resolve()

    if path.parent != base:
        raise ValueError("Invalid file path")

    if not path.exists():
        raise FileNotFoundError(path)

    return path


def render_static_video(
    *,
    audio_dir: Path,
    artwork_dir: Path,
    output_dir: Path,
    audio_filename: str,
    artwork_filename: str,
    output_filename: str,
    width: int = 1920,
    height: int = 1080,
    frame_rate: int = 30,
) -> Path:
    if not ffmpeg_available():
        raise RuntimeError("FFmpeg is required for MP4 rendering.")

    audio_path = _safe_file(
        audio_dir,
        audio_filename,
        {".wav", ".flac", ".mp3"},
    )
    artwork_path = _safe_file(
        artwork_dir,
        artwork_filename,
        {".png", ".jpg", ".jpeg"},
    )

    if Path(output_filename).name != output_filename:
        raise ValueError("Invalid output filename")

    if not output_filename.lower().endswith(".mp4"):
        raise ValueError("Output filename must end with .mp4")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = (output_dir / output_filename).resolve()

    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-loop",
        "1",
        "-framerate",
        str(frame_rate),
        "-i",
        str(artwork_path),
        "-i",
        str(audio_path),
        "-vf",
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-tune",
        "stillimage",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-pix_fmt",
        "yuv420p",
        "-shortest",
        "-movflags",
        "+faststart",
        str(output_path),
    ]

    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            completed.stderr.strip()
            or f"FFmpeg failed with exit code {completed.returncode}."
        )

    if not output_path.exists():
        raise RuntimeError("Rendered MP4 file was not created.")

    return output_path
EOF

cat > apps/api/app/services/export_bundle.py <<'EOF'
import hashlib
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)

    return digest.hexdigest()


def _resolve_existing_file(
    base_dir: Path,
    filename: str,
    allowed_suffixes: set[str],
) -> Path:
    if not filename or Path(filename).name != filename:
        raise ValueError("Invalid filename")

    if Path(filename).suffix.lower() not in allowed_suffixes:
        raise ValueError(f"Unsupported file type: {filename}")

    base = base_dir.resolve()
    path = (base / filename).resolve()

    if path.parent != base:
        raise ValueError("Invalid file path")

    if not path.exists():
        raise FileNotFoundError(path)

    return path


def create_export_bundle(
    *,
    title: str,
    audio_dir: Path,
    artwork_dir: Path,
    video_dir: Path,
    export_dir: Path,
    audio_filename: str,
    artwork_filename: str | None,
    video_filename: str | None,
    metadata: dict,
) -> tuple[Path, Path]:
    package_id = str(uuid.uuid4())
    package_root = export_dir / package_id
    package_root.mkdir(parents=True, exist_ok=True)

    audio_path = _resolve_existing_file(
        audio_dir,
        audio_filename,
        {".wav", ".flac", ".mp3"},
    )

    copied_files: list[dict] = []

    def copy_asset(source: Path, role: str) -> None:
        destination = package_root / source.name
        shutil.copy2(source, destination)
        copied_files.append(
            {
                "role": role,
                "filename": destination.name,
                "size_bytes": destination.stat().st_size,
                "sha256": sha256_file(destination),
            }
        )

    copy_asset(audio_path, "audio")

    if artwork_filename:
        artwork_path = _resolve_existing_file(
            artwork_dir,
            artwork_filename,
            {".png", ".jpg", ".jpeg"},
        )
        copy_asset(artwork_path, "artwork")

    if video_filename:
        video_path = _resolve_existing_file(
            video_dir,
            video_filename,
            {".mp4"},
        )
        copy_asset(video_path, "video")

    metadata_path = package_root / "metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    copied_files.append(
        {
            "role": "metadata",
            "filename": metadata_path.name,
            "size_bytes": metadata_path.stat().st_size,
            "sha256": sha256_file(metadata_path),
        }
    )

    manifest = {
        "package_id": package_id,
        "title": title,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": copied_files,
        "approval_required_before_publish": True,
        "publishing_status": "not_published",
    }

    manifest_path = package_root / "catalog-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    zip_path = export_dir / f"{package_id}.zip"

    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for file_path in package_root.iterdir():
            if file_path.is_file():
                archive.write(file_path, file_path.name)

    return manifest_path, zip_path
EOF

cat >> apps/api/app/schemas/visuals.py <<'EOF'


class VideoRenderRequest(BaseModel):
    audio_filename: str = Field(min_length=1, max_length=500)
    artwork_filename: str = Field(min_length=1, max_length=500)
    output_filename: str = Field(min_length=1, max_length=500)
    width: int = Field(default=1920, ge=320, le=7680)
    height: int = Field(default=1080, ge=240, le=4320)
    frame_rate: int = Field(default=30, ge=1, le=120)


class VideoRenderResponse(BaseModel):
    filename: str
    file_path: str


class ExportBundleRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    audio_filename: str = Field(min_length=1, max_length=500)
    artwork_filename: str | None = Field(default=None, max_length=500)
    video_filename: str | None = Field(default=None, max_length=500)
    metadata: dict


class ExportBundleResponse(BaseModel):
    manifest_filename: str
    manifest_path: str
    zip_filename: str
    zip_path: str
EOF

cat > apps/api/app/api/routes/exports.py <<'EOF'
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
EOF

python3 - <<'PY'
from pathlib import Path

path = Path("apps/api/app/main.py")
content = path.read_text(encoding="utf-8")

import_line = "from app.api.routes.exports import router as exports_router\n"

if import_line not in content:
    marker = "from app.api.routes.visuals import router as visuals_router\n"
    if marker not in content:
        raise SystemExit("Expected visuals router import was not found.")
    content = content.replace(marker, marker + import_line)

route_line = 'app.include_router(exports_router, prefix="/api/v1")\n'

if route_line not in content:
    marker = 'app.include_router(visuals_router, prefix="/api/v1")\n'
    if marker not in content:
        raise SystemExit("Expected visuals router registration was not found.")
    content = content.replace(marker, marker + route_line)

path.write_text(content, encoding="utf-8")
PY

cat > apps/api/tests/test_export_bundle.py <<'EOF'
import json
import wave
from pathlib import Path
from zipfile import ZipFile

from PIL import Image

from app.services.export_bundle import create_export_bundle


def create_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(8000)
        wav_file.writeframes(b"\x00\x00" * 8000)


def test_create_export_bundle(tmp_path: Path) -> None:
    audio_dir = tmp_path / "audio"
    artwork_dir = tmp_path / "artwork"
    video_dir = tmp_path / "video"
    export_dir = tmp_path / "exports"

    audio_dir.mkdir()
    artwork_dir.mkdir()
    video_dir.mkdir()

    audio_path = audio_dir / "sound.wav"
    artwork_path = artwork_dir / "cover.png"

    create_wav(audio_path)
    Image.new("RGB", (100, 100)).save(artwork_path)

    manifest_path, zip_path = create_export_bundle(
        title="Night Rain",
        audio_dir=audio_dir,
        artwork_dir=artwork_dir,
        video_dir=video_dir,
        export_dir=export_dir,
        audio_filename="sound.wav",
        artwork_filename="cover.png",
        video_filename=None,
        metadata={"title": "Night Rain"},
    )

    assert manifest_path.exists()
    assert zip_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    roles = {item["role"] for item in manifest["files"]}

    assert {"audio", "artwork", "metadata"} <= roles
    assert manifest["approval_required_before_publish"] is True

    with ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        assert "sound.wav" in names
        assert "cover.png" in names
        assert "metadata.json" in names
        assert "catalog-manifest.json" in names
EOF

cat > apps/api/tests/test_video_renderer.py <<'EOF'
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.video_renderer import render_static_video


def test_video_render_requires_ffmpeg(tmp_path: Path) -> None:
    with patch(
        "app.services.video_renderer.ffmpeg_available",
        return_value=False,
    ):
        with pytest.raises(RuntimeError, match="FFmpeg is required"):
            render_static_video(
                audio_dir=tmp_path,
                artwork_dir=tmp_path,
                output_dir=tmp_path,
                audio_filename="missing.wav",
                artwork_filename="missing.png",
                output_filename="output.mp4",
            )


def test_invalid_output_filename_is_rejected(tmp_path: Path) -> None:
    with patch(
        "app.services.video_renderer.ffmpeg_available",
        return_value=True,
    ):
        with pytest.raises(ValueError, match="Invalid output filename"):
            render_static_video(
                audio_dir=tmp_path,
                artwork_dir=tmp_path,
                output_dir=tmp_path,
                audio_filename="audio.wav",
                artwork_filename="cover.png",
                output_filename="../output.mp4",
            )
EOF

cat > docs/07-integrations/export-bundle.md <<'EOF'
# Export Bundle

## Purpose

The export bundle packages all assets required for manual review and later publishing.

## Package Contents

- audio asset;
- optional artwork;
- optional video;
- metadata JSON;
- catalog manifest;
- SHA-256 checksums.

## Catalog Manifest

The manifest records:

- package ID;
- title;
- creation timestamp;
- included files;
- file sizes;
- checksums;
- approval requirement;
- publishing status.

## Current Publishing Status

Bundles are created with:

```text
publishing_status = not_published
```

The application does not upload automatically in this MVP.
EOF

cat > docs/11-operations/mp4-rendering.md <<'EOF'
# MP4 Rendering

## Requirement

FFmpeg must be installed.

Verify:

```bash
ffmpeg -version
```

## Endpoint

```text
POST /api/v1/exports/video/render
```

Example:

```json
{
  "audio_filename": "sound.wav",
  "artwork_filename": "cover.png",
  "output_filename": "night-rain.mp4",
  "width": 1920,
  "height": 1080,
  "frame_rate": 30
}
```

## Export Bundle

```text
POST /api/v1/exports/bundle
```

The generated ZIP can contain audio, artwork, video, metadata and a catalog manifest.
EOF

echo "AION Update 018 applied successfully."
echo "Backup created at: ${BACKUP_DIR}"
echo
echo "Remaining planned updates after this one: 2"
echo
echo "Run:"
echo "  cd \"${TARGET}\""
echo "  make test"
