import json
import subprocess
import wave
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from app.services.video_renderer import ffmpeg_available, render_static_video


def test_video_render_requires_ffmpeg(tmp_path: Path) -> None:
    with patch(
        "app.services.video_renderer.ffmpeg_available",
        return_value=False,
    ):
        with pytest.raises(RuntimeError, match="FFmpeg is required"):
            render_static_video(
                audio_dir=tmp_path,
                artwork_dir=tmp_path,
                output_dir=tmp_path,
                audio_filename="missing.wav",
                artwork_filename="missing.png",
                output_filename="output.mp4",
            )


@pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg/ffprobe not available on this machine")
def test_real_render_decouples_input_from_output_frame_rate(tmp_path: Path) -> None:
    # Real regression test for the efficiency fix: input frame rate is a
    # low, fixed 2fps (not tied to the requested output frame_rate), but
    # the DELIVERED file must still be a normal, fully-populated stream at
    # the requested frame_rate -- verified with real ffprobe output, not
    # assumed safe just because the ffmpeg flags look right.
    audio_path = tmp_path / "audio.wav"
    with wave.open(str(audio_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(8000)
        wav_file.writeframes(b"\x00\x00" * 8000 * 3)  # 3 real seconds

    artwork_path = tmp_path / "cover.png"
    Image.new("RGB", (100, 100)).save(artwork_path)

    output_path = render_static_video(
        audio_dir=tmp_path,
        artwork_dir=tmp_path,
        output_dir=tmp_path,
        audio_filename="audio.wav",
        artwork_filename="cover.png",
        output_filename="output.mp4",
        width=320,
        height=240,
        frame_rate=30,
    )

    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=r_frame_rate,nb_frames",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    probe_data = json.loads(probe.stdout)

    assert probe_data["streams"][0]["r_frame_rate"] == "30/1"
    # ~3 real seconds at 30fps should be ~90 frames, not the ~6 the old
    # 2fps-everywhere behavior would have produced.
    assert int(probe_data["streams"][0]["nb_frames"]) >= 80
    assert float(probe_data["format"]["duration"]) == pytest.approx(3.0, abs=0.2)


def test_invalid_output_filename_is_rejected(tmp_path: Path) -> None:
    with patch(
        "app.services.video_renderer.ffmpeg_available",
        return_value=True,
    ):
        with pytest.raises(ValueError, match="Invalid output filename"):
            render_static_video(
                audio_dir=tmp_path,
                artwork_dir=tmp_path,
                output_dir=tmp_path,
                audio_filename="audio.wav",
                artwork_filename="cover.png",
                output_filename="../output.mp4",
            )
