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
