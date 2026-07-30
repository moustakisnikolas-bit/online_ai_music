import shutil
import subprocess
from pathlib import Path

# The still-image input only ever needs enough frames for ffmpeg's filter
# graph (scale/pad) to run against -- every one of those frames is
# bit-identical, so decoding/filtering at the real output frame_rate (30fps
# default) wastes real encode time for nothing: a 1-hour render would walk
# the filter graph 108,000 times instead of this. Decoupled from the
# output frame_rate below so the delivered file is still a normal, fully-
# populated stream (avoids any risk of looking wrong in players that
# handle sparse keyframes badly) -- verified with a real ffprobe-based
# test (test_video_renderer.py), not just assumed safe.
_INPUT_FRAME_RATE = 2


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

    # 2-second GOP at the real output frame_rate -- frequent enough
    # keyframes for YouTube's ingest pipeline and local scrubbing on a
    # still-image video (libx264's own default GOP, ~250 frames/~8s at
    # 30fps, is fairly sparse for an hour of nothing-but-a-static-image).
    gop_size = frame_rate * 2

    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-loop",
        "1",
        "-framerate",
        str(_INPUT_FRAME_RATE),
        "-i",
        str(artwork_path),
        "-i",
        str(audio_path),
        "-vf",
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
        "-r",
        str(frame_rate),
        "-g",
        str(gop_size),
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
