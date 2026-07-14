#!/usr/bin/env bash
set -Eeuo pipefail

TARGET="${1:-/Users/nikolas/Documents/GitHub/online_ai_music/online_ai_music_repo_setup}"

if [[ ! -d "${TARGET}" ]]; then
  echo "ERROR: Target directory does not exist: ${TARGET}" >&2
  exit 1
fi

cd "${TARGET}"

BACKUP_DIR="${TARGET}/.aion/backups/update-011-$(date +%Y%m%d-%H%M%S)"
mkdir -p "${BACKUP_DIR}"

backup_file() {
  local path="$1"
  if [[ -f "${path}" ]]; then
    local relative="${path#${TARGET}/}"
    mkdir -p "${BACKUP_DIR}/$(dirname "${relative}")"
    cp "${path}" "${BACKUP_DIR}/${relative}"
  fi
}

for file in \
  "apps/api/app/main.py" \
  "apps/api/app/services/audio_generator.py"; do
  backup_file "${TARGET}/${file}"
done

mkdir -p apps/api/app/services
mkdir -p apps/api/app/api/routes
mkdir -p apps/api/app/schemas
mkdir -p apps/api/tests
mkdir -p docs/03-requirements
mkdir -p docs/11-operations

cat > apps/api/app/services/audio_assets.py <<'EOF'
import hashlib
import wave
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AudioAssetMetadata:
    filename: str
    file_path: str
    file_size_bytes: int
    checksum_sha256: str
    channels: int
    sample_rate: int
    sample_width_bytes: int
    frame_count: int
    duration_seconds: float


def safe_asset_path(base_dir: Path, filename: str) -> Path:
    if not filename:
        raise ValueError("filename is required")

    if Path(filename).name != filename:
        raise ValueError("nested paths are not allowed")

    if not filename.lower().endswith(".wav"):
        raise ValueError("only WAV assets are currently supported")

    base = base_dir.resolve()
    candidate = (base / filename).resolve()

    if candidate.parent != base:
        raise ValueError("invalid asset path")

    return candidate


def calculate_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)

    return digest.hexdigest()


def inspect_wav(path: Path) -> AudioAssetMetadata:
    if not path.exists():
        raise FileNotFoundError(path)

    if not path.is_file():
        raise ValueError("asset path is not a file")

    with wave.open(str(path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_rate = wav_file.getframerate()
        sample_width = wav_file.getsampwidth()
        frame_count = wav_file.getnframes()

    duration = frame_count / sample_rate if sample_rate else 0.0

    return AudioAssetMetadata(
        filename=path.name,
        file_path=str(path),
        file_size_bytes=path.stat().st_size,
        checksum_sha256=calculate_sha256(path),
        channels=channels,
        sample_rate=sample_rate,
        sample_width_bytes=sample_width,
        frame_count=frame_count,
        duration_seconds=duration,
    )
EOF

cat > apps/api/app/schemas/audio_asset.py <<'EOF'
from pydantic import BaseModel, Field


class AudioAssetMetadataResponse(BaseModel):
    filename: str
    file_size_bytes: int = Field(ge=0)
    checksum_sha256: str
    channels: int = Field(ge=1)
    sample_rate: int = Field(gt=0)
    sample_width_bytes: int = Field(gt=0)
    frame_count: int = Field(ge=0)
    duration_seconds: float = Field(ge=0)
    download_url: str
EOF

cat > apps/api/app/api/routes/audio_assets.py <<'EOF'
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
EOF

python3 - <<'PY'
from pathlib import Path

path = Path("apps/api/app/main.py")
content = path.read_text(encoding="utf-8")

import_line = "from app.api.routes.audio_assets import router as audio_assets_router\n"
if import_line not in content:
    marker = "from app.api.routes.audio_jobs import router as audio_jobs_router\n"
    if marker not in content:
        raise SystemExit("Expected audio_jobs import was not found.")
    content = content.replace(marker, marker + import_line)

route_line = 'app.include_router(audio_assets_router, prefix="/api/v1")\n'
if route_line not in content:
    marker = 'app.include_router(audio_jobs_router, prefix="/api/v1")\n'
    if marker not in content:
        raise SystemExit("Expected audio_jobs router registration was not found.")
    content = content.replace(marker, marker + route_line)

path.write_text(content, encoding="utf-8")
PY

cat > apps/api/tests/test_audio_assets.py <<'EOF'
import wave
from pathlib import Path

import pytest

from app.services.audio_assets import (
    calculate_sha256,
    inspect_wav,
    safe_asset_path,
)


def create_test_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(2)
        wav_file.setsampwidth(2)
        wav_file.setframerate(8000)
        wav_file.writeframes(b"\x00\x00\x00\x00" * 8000)


def test_inspect_wav_returns_metadata(tmp_path: Path) -> None:
    path = tmp_path / "test.wav"
    create_test_wav(path)

    metadata = inspect_wav(path)

    assert metadata.filename == "test.wav"
    assert metadata.channels == 2
    assert metadata.sample_rate == 8000
    assert metadata.sample_width_bytes == 2
    assert metadata.frame_count == 8000
    assert metadata.duration_seconds == 1.0
    assert metadata.checksum_sha256 == calculate_sha256(path)


def test_safe_asset_path_accepts_simple_filename(tmp_path: Path) -> None:
    result = safe_asset_path(tmp_path, "asset.wav")

    assert result == (tmp_path / "asset.wav").resolve()


@pytest.mark.parametrize(
    "filename",
    [
        "../asset.wav",
        "nested/asset.wav",
        "/tmp/asset.wav",
        "asset.mp3",
        "",
    ],
)
def test_safe_asset_path_rejects_unsafe_names(
    tmp_path: Path,
    filename: str,
) -> None:
    with pytest.raises(ValueError):
        safe_asset_path(tmp_path, filename)
EOF

cat > apps/api/tests/test_audio_asset_api.py <<'EOF'
import wave
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

client = TestClient(app)


def test_asset_metadata_and_download(tmp_path: Path) -> None:
    settings = get_settings()
    original_dir = settings.generated_audio_dir
    settings.generated_audio_dir = str(tmp_path)

    path = tmp_path / "api-test.wav"

    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(8000)
        wav_file.writeframes(b"\x00\x00" * 8000)

    try:
        metadata_response = client.get(
            "/api/v1/audio/assets/api-test.wav"
        )

        assert metadata_response.status_code == 200
        payload = metadata_response.json()
        assert payload["filename"] == "api-test.wav"
        assert payload["sample_rate"] == 8000
        assert payload["duration_seconds"] == 1.0

        download_response = client.get(
            "/api/v1/audio/assets/api-test.wav/download"
        )

        assert download_response.status_code == 200
        assert download_response.headers["content-type"].startswith("audio/wav")
        assert len(download_response.content) > 44
    finally:
        settings.generated_audio_dir = original_dir
EOF

cat > docs/03-requirements/mvp-003-audio-asset-retrieval.md <<'EOF'
# MVP-003: Audio Asset Retrieval

## Objective

Allow generated WAV files to be inspected and downloaded safely through the API.

## Functional Requirements

- Retrieve WAV metadata by filename.
- Download a WAV file.
- Calculate SHA-256 checksum.
- Return duration, channel count, sample rate and frame count.
- Reject nested paths.
- Reject path traversal attempts.
- Return HTTP 404 for missing files.
- Return HTTP 422 for invalid WAV files.

## Endpoints

```text
GET /api/v1/audio/assets/{filename}
GET /api/v1/audio/assets/{filename}/download
```

## Current Scope

Only simple `.wav` filenames located directly inside the configured generated-audio directory are accepted.

This intentionally prevents arbitrary filesystem access.
EOF

cat > docs/11-operations/current-mvp-test-guide.md <<'EOF'
# Current MVP Test Guide

## Automated Tests

```bash
make test
```

## Local API

```bash
make api
```

Open:

```text
http://127.0.0.1:8000/docs
```

## Synchronous Audio Generation

Use:

```text
POST /api/v1/audio/generate
```

Example:

```json
{
  "title": "432 Hz Stereo Test",
  "mode": "sine",
  "channels": "stereo",
  "frequency_hz": 432,
  "duration_seconds": 5,
  "sample_rate": 44100,
  "amplitude": 0.1,
  "fade_in_seconds": 0.1,
  "fade_out_seconds": 0.1,
  "seamless_loop": false
}
```

The response contains a generated file path.

Use the returned filename with:

```text
GET /api/v1/audio/assets/{filename}
GET /api/v1/audio/assets/{filename}/download
```

## Binaural Example

```json
{
  "title": "10 Hz Alpha Binaural",
  "mode": "binaural_beats",
  "channels": "stereo",
  "left_frequency_hz": 200,
  "right_frequency_hz": 210,
  "duration_seconds": 5,
  "sample_rate": 44100,
  "amplitude": 0.1,
  "fade_in_seconds": 0.1,
  "fade_out_seconds": 0.1
}
```

## Isochronic Example

```json
{
  "title": "10 Hz Alpha Isochronic",
  "mode": "isochronic_tones",
  "channels": "mono",
  "frequency_hz": 220,
  "pulse_frequency_hz": 10,
  "modulation_depth": 1.0,
  "duration_seconds": 5,
  "sample_rate": 44100,
  "amplitude": 0.1,
  "fade_in_seconds": 0.1,
  "fade_out_seconds": 0.1
}
```
EOF

echo "AION Update 011 applied successfully."
echo "Backup created at: ${BACKUP_DIR}"
echo
echo "Run:"
echo "  cd \"${TARGET}\""
echo "  make test"
