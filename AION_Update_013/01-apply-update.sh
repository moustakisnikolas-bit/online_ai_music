#!/usr/bin/env bash
set -Eeuo pipefail

TARGET="${1:-/Users/nikolas/Documents/GitHub/online_ai_music/online_ai_music_repo_setup}"

if [[ ! -d "${TARGET}" ]]; then
  echo "ERROR: Target directory does not exist: ${TARGET}" >&2
  exit 1
fi

cd "${TARGET}"

BACKUP_DIR="${TARGET}/.aion/backups/update-013-$(date +%Y%m%d-%H%M%S)"
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
  "apps/api/app/audio/types.py" \
  "apps/api/app/audio/presets.py" \
  "apps/api/app/schemas/audio.py" \
  "apps/api/app/services/audio_generator.py" \
  "apps/api/app/main.py" \
  "apps/api/app/web/index.html"; do
  backup_file "${TARGET}/${file}"
done

mkdir -p apps/api/app/api/routes
mkdir -p apps/api/app/services
mkdir -p apps/api/app/schemas
mkdir -p apps/api/tests
mkdir -p docs/11-operations

cat > apps/api/app/audio/types.py <<'EOF'
from enum import StrEnum


class AudioMode(StrEnum):
    SINE = "sine"
    LAYERED_TONES = "layered_tones"
    WHITE_NOISE = "white_noise"
    PINK_NOISE = "pink_noise"
    BROWN_NOISE = "brown_noise"
    BINAURAL_BEATS = "binaural_beats"
    ISOCHRONIC_TONES = "isochronic_tones"
    PRESET = "preset"


class ChannelMode(StrEnum):
    MONO = "mono"
    STEREO = "stereo"


class OutputFormat(StrEnum):
    WAV = "wav"
    FLAC = "flac"
    MP3 = "mp3"
EOF

cat > apps/api/app/audio/presets.py <<'EOF'
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ToneLayer:
    frequency_hz: float
    amplitude: float


@dataclass(frozen=True)
class AudioPreset:
    name: str
    label: str
    description: str
    mode: str
    recommended_duration_seconds: int
    layers: tuple[ToneLayer, ...] = ()
    noise_amplitude: float = 0.0


PRESETS: dict[str, AudioPreset] = {
    "calm-432": AudioPreset(
        name="calm-432",
        label="Calm 432",
        description="A soft layered tone bed centered on 432 Hz.",
        mode="layered_tones",
        recommended_duration_seconds=1800,
        layers=(
            ToneLayer(frequency_hz=432.0, amplitude=0.16),
            ToneLayer(frequency_hz=216.0, amplitude=0.08),
        ),
    ),
    "focus-alpha-bed": AudioPreset(
        name="focus-alpha-bed",
        label="Focus Alpha Bed",
        description="A gentle dual-tone bed for focus-oriented ambient listening.",
        mode="layered_tones",
        recommended_duration_seconds=1800,
        layers=(
            ToneLayer(frequency_hz=220.0, amplitude=0.12),
            ToneLayer(frequency_hz=230.0, amplitude=0.12),
        ),
    ),
    "deep-brown": AudioPreset(
        name="deep-brown",
        label="Deep Brown Noise",
        description="Low-frequency-weighted noise for a deep ambient background.",
        mode="brown_noise",
        recommended_duration_seconds=3600,
        noise_amplitude=0.22,
    ),
    "soft-pink": AudioPreset(
        name="soft-pink",
        label="Soft Pink Noise",
        description="Balanced pink noise with a softer high-frequency profile.",
        mode="pink_noise",
        recommended_duration_seconds=3600,
        noise_amplitude=0.18,
    ),
}


def get_preset(name: str) -> AudioPreset:
    try:
        return PRESETS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown audio preset: {name}") from exc


def list_presets() -> list[dict]:
    result: list[dict] = []

    for preset in PRESETS.values():
        payload = asdict(preset)
        payload["layers"] = [asdict(layer) for layer in preset.layers]
        result.append(payload)

    return sorted(result, key=lambda item: item["label"])
EOF

python3 - <<'PY'
from pathlib import Path

path = Path("apps/api/app/schemas/audio.py")
content = path.read_text(encoding="utf-8")

content = content.replace(
    "from app.audio.types import AudioMode, ChannelMode",
    "from app.audio.types import AudioMode, ChannelMode, OutputFormat",
)

content = content.replace(
    "    seed: int | None = None\n",
    "    seed: int | None = None\n    output_format: OutputFormat = OutputFormat.WAV\n",
    1,
)

content = content.replace(
    "    status: str\n    file_path: str\n",
    "    status: str\n    output_format: str\n    file_path: str\n",
)

path.write_text(content, encoding="utf-8")
PY

cat > apps/api/app/services/audio_encoding.py <<'EOF'
import shutil
import subprocess
from pathlib import Path


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def encode_audio(
    source_wav: Path,
    output_format: str,
) -> Path:
    normalized = output_format.lower()

    if normalized == "wav":
        return source_wav

    if normalized not in {"flac", "mp3"}:
        raise ValueError(f"Unsupported output format: {output_format}")

    if not ffmpeg_available():
        raise RuntimeError(
            f"FFmpeg is required to generate {normalized.upper()} output."
        )

    output_path = source_wav.with_suffix(f".{normalized}")

    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source_wav),
    ]

    if normalized == "mp3":
        command.extend(["-codec:a", "libmp3lame", "-b:a", "192k"])

    command.append(str(output_path))

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
        raise RuntimeError("Encoded output file was not created.")

    return output_path
EOF

python3 - <<'PY'
from pathlib import Path

path = Path("apps/api/app/services/audio_generator.py")
content = path.read_text(encoding="utf-8")

import_marker = "from app.audio.types import AudioMode, ChannelMode\n"
replacement_import = (
    "from app.audio.types import AudioMode, ChannelMode\n"
    "from app.services.audio_encoding import encode_audio\n"
)
if import_marker not in content:
    raise SystemExit("Expected audio type import not found.")
content = content.replace(import_marker, replacement_import)

old = """    _write_wav(output_path, request.sample_rate, channels)

    response_frequency = (
"""
new = """    _write_wav(output_path, request.sample_rate, channels)

    final_output_path = encode_audio(
        source_wav=output_path,
        output_format=request.output_format.value,
    )

    response_frequency = (
"""

if old not in content:
    raise SystemExit("Expected WAV write block not found.")

content = content.replace(old, new)

old_response = """        status="generated",
        file_path=str(output_path),
"""
new_response = """        status="generated",
        output_format=request.output_format.value,
        file_path=str(final_output_path),
"""

if old_response not in content:
    raise SystemExit("Expected response output block not found.")

path.write_text(content.replace(old_response, new_response), encoding="utf-8")
PY

cat > apps/api/app/schemas/preset.py <<'EOF'
from pydantic import BaseModel


class PresetLayerResponse(BaseModel):
    frequency_hz: float
    amplitude: float


class PresetResponse(BaseModel):
    name: str
    label: str
    description: str
    mode: str
    recommended_duration_seconds: int
    layers: list[PresetLayerResponse]
    noise_amplitude: float
EOF

cat > apps/api/app/api/routes/presets.py <<'EOF'
from fastapi import APIRouter, HTTPException, status

from app.audio.presets import get_preset, list_presets
from app.schemas.preset import PresetResponse

router = APIRouter(prefix="/audio/presets", tags=["audio-presets"])


@router.get("", response_model=list[PresetResponse])
def list_audio_presets() -> list[dict]:
    return list_presets()


@router.get("/{preset_name}", response_model=PresetResponse)
def get_audio_preset(preset_name: str) -> dict:
    try:
        preset = get_preset(preset_name)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return {
        "name": preset.name,
        "label": preset.label,
        "description": preset.description,
        "mode": preset.mode,
        "recommended_duration_seconds": preset.recommended_duration_seconds,
        "layers": [
            {
                "frequency_hz": layer.frequency_hz,
                "amplitude": layer.amplitude,
            }
            for layer in preset.layers
        ],
        "noise_amplitude": preset.noise_amplitude,
    }
EOF

python3 - <<'PY'
from pathlib import Path

path = Path("apps/api/app/main.py")
content = path.read_text(encoding="utf-8")

import_line = "from app.api.routes.presets import router as presets_router\n"
if import_line not in content:
    marker = "from app.api.routes.projects import router as projects_router\n"
    if marker not in content:
        raise SystemExit("Expected projects import not found.")
    content = content.replace(marker, marker + import_line)

route_line = 'app.include_router(presets_router, prefix="/api/v1")\n'
if route_line not in content:
    marker = 'app.include_router(projects_router, prefix="/api/v1")\n'
    if marker not in content:
        raise SystemExit("Expected projects route registration not found.")
    content = content.replace(marker, marker + route_line)

path.write_text(content, encoding="utf-8")
PY

python3 - <<'PY'
from pathlib import Path

path = Path("apps/api/app/web/index.html")
content = path.read_text(encoding="utf-8")

old_select = """        <label id="preset-group" class="hidden">
          Preset
          <select id="preset">
            <option value="calm-432">Calm 432</option>
            <option value="focus-alpha-bed">Focus Alpha Bed</option>
            <option value="deep-brown">Deep Brown</option>
            <option value="soft-pink">Soft Pink</option>
          </select>
        </label>
"""

new_select = """        <label id="preset-group" class="hidden">
          Preset
          <select id="preset">
            <option value="">Loading presets…</option>
          </select>
        </label>

        <label>
          Output format
          <select id="output-format">
            <option value="wav" selected>WAV</option>
            <option value="flac">FLAC</option>
            <option value="mp3">MP3</option>
          </select>
        </label>
"""

if old_select not in content:
    raise SystemExit("Expected preset selector block not found.")

content = content.replace(old_select, new_select)

old_payload = """      seed: Number(document.getElementById("seed").value)
    };
"""

new_payload = """      seed: Number(document.getElementById("seed").value),
      output_format: document.getElementById("output-format").value
    };
"""

if old_payload not in content:
    raise SystemExit("Expected payload block not found.")

content = content.replace(old_payload, new_payload)

old_filename_logic = """      const filename = body.file_path.split("/").pop();
      const metadataUrl = `/api/v1/audio/assets/${encodeURIComponent(filename)}`;
"""

new_filename_logic = """      const filename = body.file_path.split("/").pop();

      if (!filename.toLowerCase().endsWith(".wav")) {
        document.getElementById("filename").textContent = filename;
        document.getElementById("result-mode").textContent = body.mode;
        document.getElementById("result-duration").textContent =
          document.getElementById("duration").value;
        document.getElementById("result-rate").textContent =
          document.getElementById("sample-rate").value;
        document.getElementById("player").src = "";
        document.getElementById("download").href =
          `/api/v1/audio/files/${encodeURIComponent(filename)}`;
        success.style.display = "block";
        result.classList.add("visible");
        status.textContent = "Completed";
        return;
      }

      const metadataUrl = `/api/v1/audio/assets/${encodeURIComponent(filename)}`;
"""

if old_filename_logic not in content:
    raise SystemExit("Expected filename logic block not found.")

content = content.replace(old_filename_logic, new_filename_logic)

insert_marker = """  mode.addEventListener("change", updateConditionalFields);
  updateConditionalFields();
"""

insert_replacement = """  async function loadPresets() {
    const presetSelect = document.getElementById("preset");

    try {
      const response = await fetch("/api/v1/audio/presets");
      const presets = await response.json();

      if (!response.ok) {
        throw new Error("Unable to load presets.");
      }

      presetSelect.innerHTML = "";

      for (const preset of presets) {
        const option = document.createElement("option");
        option.value = preset.name;
        option.textContent = `${preset.label} — ${preset.description}`;
        presetSelect.appendChild(option);
      }
    } catch (exception) {
      presetSelect.innerHTML =
        '<option value="calm-432">Calm 432</option>';
    }
  }

  mode.addEventListener("change", updateConditionalFields);
  updateConditionalFields();
  loadPresets();
"""

if insert_marker not in content:
    raise SystemExit("Expected UI initialization marker not found.")

path.write_text(
    content.replace(insert_marker, insert_replacement),
    encoding="utf-8",
)
PY

cat > apps/api/app/api/routes/audio_files.py <<'EOF'
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
EOF

python3 - <<'PY'
from pathlib import Path

path = Path("apps/api/app/main.py")
content = path.read_text(encoding="utf-8")

import_line = "from app.api.routes.audio_files import router as audio_files_router\n"
if import_line not in content:
    marker = "from app.api.routes.audio_assets import router as audio_assets_router\n"
    if marker not in content:
        raise SystemExit("Expected audio assets import not found.")
    content = content.replace(marker, marker + import_line)

route_line = 'app.include_router(audio_files_router, prefix="/api/v1")\n'
if route_line not in content:
    marker = 'app.include_router(audio_assets_router, prefix="/api/v1")\n'
    if marker not in content:
        raise SystemExit("Expected audio assets route registration not found.")
    content = content.replace(marker, marker + route_line)

path.write_text(content, encoding="utf-8")
PY

cat > apps/api/tests/test_presets_api.py <<'EOF'
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_presets() -> None:
    response = client.get("/api/v1/audio/presets")

    assert response.status_code == 200
    payload = response.json()

    assert len(payload) >= 4
    assert any(item["name"] == "calm-432" for item in payload)


def test_get_unknown_preset_returns_404() -> None:
    response = client.get("/api/v1/audio/presets/does-not-exist")

    assert response.status_code == 404
EOF

cat > apps/api/tests/test_audio_encoding.py <<'EOF'
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.audio_encoding import encode_audio


def test_wav_encoding_returns_original_path(tmp_path: Path) -> None:
    source = tmp_path / "source.wav"
    source.write_bytes(b"RIFF")

    assert encode_audio(source, "wav") == source


def test_encoded_format_requires_ffmpeg(tmp_path: Path) -> None:
    source = tmp_path / "source.wav"
    source.write_bytes(b"RIFF")

    with patch(
        "app.services.audio_encoding.ffmpeg_available",
        return_value=False,
    ):
        with pytest.raises(RuntimeError, match="FFmpeg is required"):
            encode_audio(source, "mp3")


def test_unknown_format_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source.wav"
    source.write_bytes(b"RIFF")

    with pytest.raises(ValueError, match="Unsupported output format"):
        encode_audio(source, "aac")
EOF

cat > docs/11-operations/audio-formats.md <<'EOF'
# Audio Output Formats

## WAV

WAV output is generated directly by Python and requires no external encoder.

## FLAC

FLAC output requires FFmpeg.

## MP3

MP3 output requires FFmpeg with MP3 encoder support.

## Verification

```bash
ffmpeg -version
```

## Local UI

The web interface allows selecting:

- WAV;
- FLAC;
- MP3.

When FFmpeg is unavailable, WAV remains fully functional and FLAC or MP3 requests return an explicit error.
EOF

echo "AION Update 013 applied successfully."
echo "Backup created at: ${BACKUP_DIR}"
echo
echo "Run:"
echo "  cd \"${TARGET}\""
echo "  make test"
echo "  make api"
