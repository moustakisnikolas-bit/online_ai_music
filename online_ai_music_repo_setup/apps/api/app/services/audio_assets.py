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
