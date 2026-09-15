from pathlib import Path

from PIL import Image

from app.services.artwork_generator import PRESETS, composite_thumbnail_labels, generate_artwork


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


def test_youtube_shorts_preset_is_vertical_1080x1920() -> None:
    preset = PRESETS["youtube-shorts"]

    assert (preset.width, preset.height) == (1080, 1920)


def test_generate_youtube_shorts_artwork(tmp_path: Path) -> None:
    path = generate_artwork(
        title="Night Rain",
        subtitle="Original Sleep Audio",
        preset_name="youtube-shorts",
        output_dir=tmp_path,
        seed=7,
    )

    with Image.open(path) as image:
        assert image.size == (1080, 1920)


def test_composite_thumbnail_labels_preserves_size_and_format(tmp_path: Path) -> None:
    path = tmp_path / "photo.png"
    Image.new("RGB", (1280, 720), (60, 90, 140)).save(path, format="PNG")

    composite_thumbnail_labels(path, headline="FOCUS", subline="432 Hz")

    with Image.open(path) as image:
        assert image.size == (1280, 720)
        assert image.format == "PNG"


def test_composite_thumbnail_labels_actually_changes_pixels(tmp_path: Path) -> None:
    path = tmp_path / "photo.png"
    # Flat mid-grey -- any text/scrim compositing will visibly change
    # some pixels, so a real change here proves drawing actually
    # happened, not just that the file was re-saved untouched.
    Image.new("RGB", (1280, 720), (128, 128, 128)).save(path, format="PNG")

    with Image.open(path) as before:
        before_pixels = list(before.getdata())

    composite_thumbnail_labels(path, headline="FOCUS", subline="432 Hz")

    with Image.open(path) as after:
        after_pixels = list(after.getdata())

    assert before_pixels != after_pixels


def test_composite_thumbnail_labels_stays_under_youtube_thumbnail_limit(tmp_path: Path) -> None:
    path = tmp_path / "photo.png"
    Image.new("RGB", (1280, 720), (60, 90, 140)).save(path, format="PNG")

    composite_thumbnail_labels(path, headline="RELAXATION", subline="396 Hz")

    assert path.stat().st_size < 2 * 1024 * 1024
