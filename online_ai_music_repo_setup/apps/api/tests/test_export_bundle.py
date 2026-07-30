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
    caption_dir = tmp_path / "captions"
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
        caption_dir=caption_dir,
        export_dir=export_dir,
        audio_filename="sound.wav",
        artwork_filename="cover.png",
        video_filename=None,
        caption_filename=None,
        metadata={"title": "Night Rain"},
    )

    assert manifest_path.exists()
    assert zip_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    roles = {item["role"] for item in manifest["files"]}

    assert {"audio", "artwork", "metadata"} <= roles
    assert "captions" not in roles
    assert manifest["approval_required_before_publish"] is True

    with ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        assert "sound.wav" in names
        assert "cover.png" in names
        assert "metadata.json" in names
        assert "catalog-manifest.json" in names


def test_create_export_bundle_includes_captions_when_present(tmp_path: Path) -> None:
    audio_dir = tmp_path / "audio"
    artwork_dir = tmp_path / "artwork"
    video_dir = tmp_path / "video"
    caption_dir = tmp_path / "captions"
    export_dir = tmp_path / "exports"

    audio_dir.mkdir()
    artwork_dir.mkdir()
    video_dir.mkdir()
    caption_dir.mkdir()

    audio_path = audio_dir / "sound.wav"
    create_wav(audio_path)

    caption_path = caption_dir / "sound.srt"
    caption_path.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nHello\n\n",
        encoding="utf-8",
    )

    manifest_path, zip_path = create_export_bundle(
        title="Night Rain",
        audio_dir=audio_dir,
        artwork_dir=artwork_dir,
        video_dir=video_dir,
        caption_dir=caption_dir,
        export_dir=export_dir,
        audio_filename="sound.wav",
        artwork_filename=None,
        video_filename=None,
        caption_filename="sound.srt",
        metadata={"title": "Night Rain"},
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    roles = {item["role"] for item in manifest["files"]}
    assert "captions" in roles

    with ZipFile(zip_path) as archive:
        assert "sound.srt" in archive.namelist()
