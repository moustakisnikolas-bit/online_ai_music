#!/usr/bin/env bash
set -Eeuo pipefail

TARGET="${1:-/Users/nikolas/Documents/GitHub/online_ai_music/online_ai_music_repo_setup}"

if [[ ! -d "${TARGET}" ]]; then
  echo "ERROR: Target directory does not exist: ${TARGET}" >&2
  exit 1
fi

cd "${TARGET}"

BACKUP_DIR="${TARGET}/.aion/backups/update-017-$(date +%Y%m%d-%H%M%S)"
mkdir -p "${BACKUP_DIR}"

for file in \
  "requirements/runtime.txt" \
  "apps/api/app/main.py"; do
  if [[ -f "${file}" ]]; then
    mkdir -p "${BACKUP_DIR}/$(dirname "${file}")"
    cp "${file}" "${BACKUP_DIR}/${file}"
  fi
done

mkdir -p apps/api/app/services
mkdir -p apps/api/app/schemas
mkdir -p apps/api/app/api/routes
mkdir -p apps/api/tests
mkdir -p data/generated/artwork
mkdir -p data/generated/video
mkdir -p docs/06-factories/visuals
mkdir -p docs/11-operations

if ! grep -Fqx "pillow>=11.0,<12.0" requirements/runtime.txt; then
  printf '%s\n' "pillow>=11.0,<12.0" >> requirements/runtime.txt
fi

cat > apps/api/app/services/artwork_generator.py <<'EOF'
import hashlib
import math
import random
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


@dataclass(frozen=True)
class ArtworkPreset:
    width: int
    height: int
    label: str


PRESETS: dict[str, ArtworkPreset] = {
    "spotify-cover": ArtworkPreset(
        width=3000,
        height=3000,
        label="Spotify / Distributor Cover",
    ),
    "youtube-thumbnail": ArtworkPreset(
        width=1280,
        height=720,
        label="YouTube Thumbnail",
    ),
    "square-preview": ArtworkPreset(
        width=1080,
        height=1080,
        label="Square Preview",
    ),
}


def safe_filename(value: str) -> str:
    cleaned = "".join(
        character.lower() if character.isalnum() else "-"
        for character in value.strip()
    )
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned or "aion-artwork"


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]

    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)

    return ImageFont.load_default()


def _gradient_background(
    width: int,
    height: int,
    seed: int,
) -> Image.Image:
    generator = random.Random(seed)
    start = (
        generator.randint(5, 45),
        generator.randint(20, 70),
        generator.randint(60, 130),
    )
    end = (
        generator.randint(20, 80),
        generator.randint(5, 45),
        generator.randint(40, 100),
    )

    image = Image.new("RGB", (width, height))
    pixels = image.load()

    for y in range(height):
        ratio = y / max(1, height - 1)
        color = tuple(
            int(start[index] * (1 - ratio) + end[index] * ratio)
            for index in range(3)
        )
        for x in range(width):
            pixels[x, y] = color

    return image


def _draw_ambient_orbs(
    image: Image.Image,
    seed: int,
) -> None:
    generator = random.Random(seed)
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    width, height = image.size
    count = 18

    for _ in range(count):
        radius = generator.randint(
            max(20, min(width, height) // 30),
            max(40, min(width, height) // 7),
        )
        center_x = generator.randint(-radius, width + radius)
        center_y = generator.randint(-radius, height + radius)
        color = (
            generator.randint(80, 180),
            generator.randint(120, 220),
            generator.randint(180, 255),
            generator.randint(20, 75),
        )
        draw.ellipse(
            (
                center_x - radius,
                center_y - radius,
                center_x + radius,
                center_y + radius,
            ),
            fill=color,
        )

    blurred = overlay.filter(
        ImageFilter.GaussianBlur(
            radius=max(12, min(width, height) // 45)
        )
    )
    image.paste(blurred, (0, 0), blurred)


def _fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    initial_size: int,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    size = initial_size

    while size >= 18:
        font = _font(size)
        box = draw.textbbox((0, 0), text, font=font)

        if box[2] - box[0] <= max_width:
            return font

        size -= 4

    return _font(18)


def generate_artwork(
    *,
    title: str,
    subtitle: str,
    preset_name: str,
    output_dir: Path,
    seed: int = 42,
) -> Path:
    if preset_name not in PRESETS:
        raise ValueError(f"Unknown artwork preset: {preset_name}")

    preset = PRESETS[preset_name]
    output_dir.mkdir(parents=True, exist_ok=True)

    image = _gradient_background(
        preset.width,
        preset.height,
        seed,
    )
    _draw_ambient_orbs(image, seed + 1)

    draw = ImageDraw.Draw(image)
    margin = int(preset.width * 0.08)
    max_width = preset.width - (margin * 2)

    title_font = _fit_text(
        draw,
        title,
        max_width,
        max(54, preset.width // 14),
    )
    subtitle_font = _fit_text(
        draw,
        subtitle,
        max_width,
        max(28, preset.width // 30),
    )

    title_box = draw.textbbox(
        (0, 0),
        title,
        font=title_font,
    )
    title_height = title_box[3] - title_box[1]
    title_y = int(preset.height * 0.62)

    shadow_offset = max(2, preset.width // 500)

    draw.text(
        (margin + shadow_offset, title_y + shadow_offset),
        title,
        font=title_font,
        fill=(0, 0, 0, 150),
    )
    draw.text(
        (margin, title_y),
        title,
        font=title_font,
        fill=(245, 248, 255),
    )

    subtitle_y = title_y + title_height + int(preset.height * 0.025)

    draw.text(
        (margin, subtitle_y),
        subtitle,
        font=subtitle_font,
        fill=(205, 220, 240),
    )

    brand_text = "AION"
    brand_font = _font(max(20, preset.width // 65))

    draw.text(
        (margin, margin),
        brand_text,
        font=brand_font,
        fill=(220, 235, 255),
    )

    identity = hashlib.sha256(
        f"{title}|{subtitle}|{preset_name}|{seed}".encode("utf-8")
    ).hexdigest()[:12]

    filename = (
        f"{safe_filename(title)}-{preset_name}-{identity}.png"
    )
    output_path = output_dir / filename
    image.save(output_path, format="PNG", optimize=True)

    return output_path
EOF

cat > apps/api/app/services/video_package.py <<'EOF'
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class VideoRenderManifest:
    title: str
    audio_filename: str
    artwork_filename: str
    duration_seconds: int
    width: int
    height: int
    frame_rate: int
    output_filename: str
    render_mode: str


def create_video_manifest(
    *,
    title: str,
    audio_filename: str,
    artwork_filename: str,
    duration_seconds: int,
    output_dir: Path,
    width: int = 1920,
    height: int = 1080,
    frame_rate: int = 30,
    render_mode: str = "static_artwork",
) -> Path:
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")

    output_dir.mkdir(parents=True, exist_ok=True)

    safe_stem = "".join(
        character.lower() if character.isalnum() else "-"
        for character in title
    )
    safe_stem = "-".join(
        part for part in safe_stem.split("-") if part
    ) or "aion-video"

    manifest = VideoRenderManifest(
        title=title,
        audio_filename=audio_filename,
        artwork_filename=artwork_filename,
        duration_seconds=duration_seconds,
        width=width,
        height=height,
        frame_rate=frame_rate,
        output_filename=f"{safe_stem}.mp4",
        render_mode=render_mode,
    )

    path = output_dir / f"{safe_stem}.video-manifest.json"
    path.write_text(
        json.dumps(
            asdict(manifest),
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    return path
EOF

cat > apps/api/app/schemas/visuals.py <<'EOF'
from pydantic import BaseModel, Field


class ArtworkGenerateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    subtitle: str = Field(default="Original Ambient Audio", max_length=255)
    preset_name: str = Field(default="spotify-cover", max_length=100)
    seed: int = 42


class ArtworkGenerateResponse(BaseModel):
    filename: str
    file_path: str
    preset_name: str
    width: int
    height: int


class VideoManifestRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    audio_filename: str = Field(min_length=1, max_length=500)
    artwork_filename: str = Field(min_length=1, max_length=500)
    duration_seconds: int = Field(gt=0, le=28800)
    width: int = Field(default=1920, ge=320, le=7680)
    height: int = Field(default=1080, ge=240, le=4320)
    frame_rate: int = Field(default=30, ge=1, le=120)


class VideoManifestResponse(BaseModel):
    manifest_filename: str
    manifest_path: str
EOF

cat > apps/api/app/api/routes/visuals.py <<'EOF'
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
EOF

python3 - <<'PY'
from pathlib import Path

path = Path("apps/api/app/main.py")
content = path.read_text(encoding="utf-8")

import_line = "from app.api.routes.visuals import router as visuals_router\n"

if import_line not in content:
    marker = "from app.api.routes.web import router as web_router\n"

    if marker not in content:
        raise SystemExit("Expected web router import was not found.")

    content = content.replace(marker, marker + import_line)

route_line = 'app.include_router(visuals_router, prefix="/api/v1")\n'

if route_line not in content:
    marker = "app.include_router(web_router)\n"

    if marker not in content:
        raise SystemExit("Expected web router registration was not found.")

    content = content.replace(marker, route_line + marker)

path.write_text(content, encoding="utf-8")
PY

cat > apps/api/tests/test_artwork_generator.py <<'EOF'
from pathlib import Path

from PIL import Image

from app.services.artwork_generator import generate_artwork


def test_generate_square_artwork(tmp_path: Path) -> None:
    path = generate_artwork(
        title="Night Rain",
        subtitle="Original Sleep Audio",
        preset_name="square-preview",
        output_dir=tmp_path,
        seed=42,
    )

    assert path.exists()

    with Image.open(path) as image:
        assert image.size == (1080, 1080)
        assert image.format == "PNG"


def test_artwork_is_deterministically_named(tmp_path: Path) -> None:
    first = generate_artwork(
        title="Brown Noise",
        subtitle="Deep Ambient",
        preset_name="youtube-thumbnail",
        output_dir=tmp_path,
        seed=12,
    )
    second = generate_artwork(
        title="Brown Noise",
        subtitle="Deep Ambient",
        preset_name="youtube-thumbnail",
        output_dir=tmp_path,
        seed=12,
    )

    assert first.name == second.name
EOF

cat > apps/api/tests/test_video_package.py <<'EOF'
import json
from pathlib import Path

from app.services.video_package import create_video_manifest


def test_create_video_manifest(tmp_path: Path) -> None:
    path = create_video_manifest(
        title="Night Rain",
        audio_filename="night-rain.wav",
        artwork_filename="night-rain.png",
        duration_seconds=600,
        output_dir=tmp_path,
    )

    assert path.exists()

    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["audio_filename"] == "night-rain.wav"
    assert payload["artwork_filename"] == "night-rain.png"
    assert payload["duration_seconds"] == 600
    assert payload["output_filename"].endswith(".mp4")
EOF

cat > apps/api/tests/test_visuals_api.py <<'EOF'
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_visual_presets_endpoint() -> None:
    response = client.get("/api/v1/visuals/presets")

    assert response.status_code == 200
    payload = response.json()
    assert any(item["name"] == "spotify-cover" for item in payload)


def test_generate_video_manifest_endpoint() -> None:
    response = client.post(
        "/api/v1/visuals/video/manifest",
        json={
            "title": "Night Rain",
            "audio_filename": "night-rain.wav",
            "artwork_filename": "night-rain.png",
            "duration_seconds": 600,
        },
    )

    assert response.status_code == 200
    assert response.json()["manifest_filename"].endswith(
        ".video-manifest.json"
    )
EOF

cat > docs/06-factories/visuals/artwork-and-video.md <<'EOF'
# Artwork and Video Packages

## Artwork Presets

### Spotify Cover

- 3000 × 3000
- square PNG
- intended for distributor and streaming cover workflows

### YouTube Thumbnail

- 1280 × 720
- landscape PNG
- intended for YouTube thumbnail workflows

### Square Preview

- 1080 × 1080
- intended for previews and social media

## Artwork Generation

Artwork is generated procedurally from:

- title;
- subtitle;
- visual preset;
- deterministic seed.

The current version does not call an external image-generation API.

## Video Manifest

The video manifest describes:

- audio filename;
- artwork filename;
- duration;
- resolution;
- frame rate;
- output filename;
- render mode.

A later rendering stage can consume the manifest and call FFmpeg.

## Copyright Position

The procedural artwork is created by the application.

Do not add third-party logos, protected characters, album artwork or recognizable artist branding.
EOF

cat > docs/11-operations/visual-package-example.md <<'EOF'
# Visual Package Example

## Generate Artwork

```text
POST /api/v1/visuals/artwork/generate
```

```json
{
  "title": "Night Rain",
  "subtitle": "Original Sleep Audio",
  "preset_name": "spotify-cover",
  "seed": 42
}
```

## Generate a Video Manifest

```text
POST /api/v1/visuals/video/manifest
```

```json
{
  "title": "Night Rain",
  "audio_filename": "night-rain.wav",
  "artwork_filename": "night-rain.png",
  "duration_seconds": 3600,
  "width": 1920,
  "height": 1080,
  "frame_rate": 30
}
```

## Current Limitation

This update creates the visual assets and render manifest.

Actual MP4 rendering is added in the next publishing/export phase.
EOF

echo "AION Update 017 applied successfully."
echo "Backup created at: ${BACKUP_DIR}"
echo
echo "Remaining planned updates after this one: 3"
echo
echo "Important:"
echo "  Run make setup once to install Pillow."
echo
echo "Then run:"
echo "  make test"
