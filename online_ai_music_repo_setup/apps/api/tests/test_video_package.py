import json
from pathlib import Path

from app.services.video_package import create_video_manifest


def test_create_video_manifest(tmp_path: Path) -> None:
    path = create_video_manifest(
        title="Night Rain",
        audio_filename="night-rain.wav",
        artwork_filename="night-rain.png",
        duration_seconds=600,
        output_dir=tmp_path,
    )

    assert path.exists()

    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["audio_filename"] == "night-rain.wav"
    assert payload["artwork_filename"] == "night-rain.png"
    assert payload["duration_seconds"] == 600
    assert payload["output_filename"].endswith(".mp4")
