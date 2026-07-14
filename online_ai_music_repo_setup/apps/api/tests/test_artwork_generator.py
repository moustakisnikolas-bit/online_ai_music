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
