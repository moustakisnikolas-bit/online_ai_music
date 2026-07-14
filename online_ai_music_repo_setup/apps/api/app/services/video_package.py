import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class VideoRenderManifest:
    title: str
    audio_filename: str
    artwork_filename: str
    duration_seconds: int
    width: int
    height: int
    frame_rate: int
    output_filename: str
    render_mode: str


def create_video_manifest(
    *,
    title: str,
    audio_filename: str,
    artwork_filename: str,
    duration_seconds: int,
    output_dir: Path,
    width: int = 1920,
    height: int = 1080,
    frame_rate: int = 30,
    render_mode: str = "static_artwork",
) -> Path:
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")

    output_dir.mkdir(parents=True, exist_ok=True)

    safe_stem = "".join(
        character.lower() if character.isalnum() else "-"
        for character in title
    )
    safe_stem = "-".join(
        part for part in safe_stem.split("-") if part
    ) or "aion-video"

    manifest = VideoRenderManifest(
        title=title,
        audio_filename=audio_filename,
        artwork_filename=artwork_filename,
        duration_seconds=duration_seconds,
        width=width,
        height=height,
        frame_rate=frame_rate,
        output_filename=f"{safe_stem}.mp4",
        render_mode=render_mode,
    )

    path = output_dir / f"{safe_stem}.video-manifest.json"
    path.write_text(
        json.dumps(
            asdict(manifest),
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    return path
