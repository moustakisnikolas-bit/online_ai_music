import shutil
import subprocess
from pathlib import Path


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _safe_file(base_dir: Path, filename: str, allowed_suffixes: set[str]) -> Path:
    if not filename or Path(filename).name != filename:
        raise ValueError("Invalid filename")

    suffix = Path(filename).suffix.lower()
    if suffix not in allowed_suffixes:
        raise ValueError(f"Unsupported file type: {suffix}")

    base = base_dir.resolve()
    path = (base / filename).resolve()

    if path.parent != base:
        raise ValueError("Invalid file path")

    if not path.exists():
        raise FileNotFoundError(path)

    return path


def render_static_video(
    *,
    audio_dir: Path,
    artwork_dir: Path,
    output_dir: Path,
    audio_filename: str,
    artwork_filename: str,
    output_filename: str,
    width: int = 1920,
    height: int = 1080,
    frame_rate: int = 30,
) -> Path:
    if not ffmpeg_available():
        raise RuntimeError("FFmpeg is required for MP4 rendering.")

    if Path(output_filename).name != output_filename:
        raise ValueError("Invalid output filename")

    if not output_filename.lower().endswith(".mp4"):
        raise ValueError("Output filename must end with .mp4")

    audio_path = _safe_file(
        audio_dir,
        audio_filename,
        {".wav", ".flac", ".mp3"},
    )
    artwork_path = _safe_file(
        artwork_dir,
        artwork_filename,
        {".png", ".jpg", ".jpeg"},
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = (output_dir / output_filename).resolve()

    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-loop",
        "1",
        "-framerate",
        str(frame_rate),
        "-i",
        str(artwork_path),
        "-i",
        str(audio_path),
        "-vf",
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-tune",
        "stillimage",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-pix_fmt",
        "yuv420p",
        "-shortest",
        "-movflags",
        "+faststart",
        str(output_path),
    ]

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
        raise RuntimeError("Rendered MP4 file was not created.")

    return output_path
