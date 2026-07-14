#!/usr/bin/env bash
set -Eeuo pipefail

TARGET="${1:-/Users/nikolas/Documents/GitHub/online_ai_music/online_ai_music_repo_setup}"

if [[ ! -d "${TARGET}" ]]; then
  echo "ERROR: Target directory does not exist: ${TARGET}" >&2
  exit 1
fi

cd "${TARGET}"

python3 - <<'PY'
from pathlib import Path

schema_path = Path("apps/api/app/schemas/audio.py")
service_path = Path("apps/api/app/services/audio_generator.py")

schema = schema_path.read_text(encoding="utf-8")
old_schema = """class AudioGenerationResponse(BaseModel):
    id: str
    title: str
    mode: str
    duration_seconds: int
"""
new_schema = """class AudioGenerationResponse(BaseModel):
    id: str
    title: str
    mode: str
    frequency_hz: float | None = None
    duration_seconds: int
"""

if old_schema not in schema:
    raise SystemExit("Expected AudioGenerationResponse block was not found.")

schema_path.write_text(
    schema.replace(old_schema, new_schema),
    encoding="utf-8",
)

service = service_path.read_text(encoding="utf-8")
old_service = """    return AudioGenerationResponse(
        id=asset_id,
        title=request.title,
        mode=request.mode.value,
        duration_seconds=request.duration_seconds,
"""
new_service = """    response_frequency = (
        request.frequency_hz
        if request.mode == AudioMode.SINE
        else None
    )

    return AudioGenerationResponse(
        id=asset_id,
        title=request.title,
        mode=request.mode.value,
        frequency_hz=response_frequency,
        duration_seconds=request.duration_seconds,
"""

if old_service not in service:
    raise SystemExit("Expected AudioGenerationResponse construction was not found.")

service_path.write_text(
    service.replace(old_service, new_service),
    encoding="utf-8",
)
PY

cat > apps/api/tests/test_audio_response_compatibility.py <<'EOF'
from pathlib import Path

from app.audio.types import AudioMode
from app.schemas.audio import AudioGenerationRequest
from app.services.audio_generator import generate_audio


def test_sine_response_includes_frequency(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="432 Hz Compatibility Test",
        mode=AudioMode.SINE,
        frequency_hz=432,
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.1,
    )

    result = generate_audio(request, tmp_path)

    assert result.frequency_hz == 432


def test_noise_response_has_no_single_frequency(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="Brown Noise Compatibility Test",
        mode=AudioMode.BROWN_NOISE,
        duration_seconds=1,
        sample_rate=8000,
        amplitude=0.1,
        fade_in_seconds=0,
        fade_out_seconds=0,
        seed=42,
    )

    result = generate_audio(request, tmp_path)

    assert result.frequency_hz is None
EOF

echo "Update 008B applied successfully."
echo
echo "Run:"
echo "  cd \"${TARGET}\""
echo "  make test"
