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
