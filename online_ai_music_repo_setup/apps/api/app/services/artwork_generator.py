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
