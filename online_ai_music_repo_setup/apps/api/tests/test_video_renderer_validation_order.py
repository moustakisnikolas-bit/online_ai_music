from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.video_renderer import render_static_video


def test_invalid_output_filename_is_checked_before_inputs(
    tmp_path: Path,
) -> None:
    with patch(
        "app.services.video_renderer.ffmpeg_available",
        return_value=True,
    ):
        with pytest.raises(ValueError, match="Invalid output filename"):
            render_static_video(
                audio_dir=tmp_path,
                artwork_dir=tmp_path,
                output_dir=tmp_path,
                audio_filename="missing.wav",
                artwork_filename="missing.png",
                output_filename="../unsafe.mp4",
            )
