import hashlib
import random
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


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


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    # PIL's load_default() fallback ignores the requested size entirely
    # (a tiny fixed bitmap font) -- silently discovered on this Windows
    # dev machine, since none of the original mac/Linux-only candidates
    # below exist here, making every text draw illegibly small regardless
    # of the size passed in. Windows paths added so this actually renders
    # at the requested size on the platform this app runs on.
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
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
    *,
    bold: bool = False,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    size = initial_size

    while size >= 18:
        font = _font(size, bold=bold)
        box = draw.textbbox((0, 0), text, font=font)

        if box[2] - box[0] <= max_width:
            return font

        size -= 4

    return _font(18, bold=bold)


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


def composite_thumbnail_labels(image_path: Path, *, headline: str, subline: str) -> None:
    """Stamps a real, guaranteed-legible headline/subline onto an
    existing image in place.

    AI image models (flux-schnell especially, tuned for speed over
    fidelity) render text unreliably -- garbled letters, misspellings.
    The AI photo is deliberately generated text-free and this composites
    real text on top afterward instead, the same way a human thumbnail
    designer layers text over a background photo rather than generating
    both together.
    """
    image = Image.open(image_path).convert("RGB")
    width, height = image.size

    # A modest, thumbnail-appropriate contrast/saturation boost -- a
    # small preview needs to read clearly at a glance, and a slightly
    # punchier image holds up better at thumbnail size than a flat one.
    image = ImageEnhance.Contrast(image).enhance(1.12)
    image = ImageEnhance.Color(image).enhance(1.15)

    # Dark scrim across the lower third so the text stays legible over
    # any photo content, not just ones that happen to already be dark
    # there -- same alpha-mask paste idiom as _draw_ambient_orbs above.
    scrim_height = int(height * 0.38)
    scrim = Image.new("RGBA", (width, scrim_height), (0, 0, 0, 0))
    scrim_draw = ImageDraw.Draw(scrim)
    for y in range(scrim_height):
        alpha = int(215 * (y / max(1, scrim_height - 1)))
        scrim_draw.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))
    image.paste(scrim, (0, height - scrim_height), scrim)

    draw = ImageDraw.Draw(image)
    margin = int(width * 0.06)
    max_width = width - (margin * 2)

    headline_font = _fit_text(draw, headline, max_width, max(80, width // 8), bold=True)
    subline_font = _fit_text(draw, subline, max_width, max(32, width // 24))

    headline_box = draw.textbbox((0, 0), headline, font=headline_font)
    headline_height = headline_box[3] - headline_box[1]
    subline_box = draw.textbbox((0, 0), subline, font=subline_font)
    subline_height = subline_box[3] - subline_box[1]

    gap = int(height * 0.02)
    subline_y = height - margin - subline_height
    headline_y = subline_y - gap - headline_height

    shadow_offset = max(2, width // 400)

    for text, font, y in (
        (headline, headline_font, headline_y),
        (subline, subline_font, subline_y),
    ):
        draw.text((margin + shadow_offset, y + shadow_offset), text, font=font, fill=(0, 0, 0))
        draw.text((margin, y), text, font=font, fill=(255, 255, 255))

    # YouTube's real custom-thumbnail cap is 2MB -- a 1280x720 PNG this
    # simple (photo + scrim + two text lines) comes in well under that in
    # practice (verified against a real generated file), so no fallback
    # compression path here.
    image.save(image_path, format="PNG", optimize=True)
