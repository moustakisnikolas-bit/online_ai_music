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


def _fake_completed_process(output_path: Path) -> subprocess.CompletedProcess:
    output_path.write_bytes(b"fake mp4 bytes")
    return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")


def _make_real_source_files(tmp_path: Path) -> None:
    audio_path = tmp_path / "audio.wav"
    with wave.open(str(audio_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(8000)
        wav_file.writeframes(b"\x00\x00" * 8000 * 3)

    Image.new("RGB", (100, 100)).save(tmp_path / "cover.png")


def test_no_audio_trim_flags_emitted_when_using_defaults(tmp_path: Path) -> None:
    # Backward-compat proof: a caller that never passes
    # audio_start_seconds/audio_duration_seconds (every existing call site)
    # must produce the exact same ffmpeg argument list as before those
    # params existed.
    _make_real_source_files(tmp_path)
    output_path = tmp_path / "output.mp4"
    captured_command = {}

    def _fake_run(command, **kwargs):
        captured_command["command"] = command
        return _fake_completed_process(output_path)

    with patch("app.services.video_renderer.ffmpeg_available", return_value=True):
        with patch("subprocess.run", side_effect=_fake_run):
            render_static_video(
                audio_dir=tmp_path,
                artwork_dir=tmp_path,
                output_dir=tmp_path,
                audio_filename="audio.wav",
                artwork_filename="cover.png",
                output_filename="output.mp4",
            )

    assert "-ss" not in captured_command["command"]
    assert "-t" not in captured_command["command"]


def test_audio_trim_flags_land_immediately_before_the_audio_input(tmp_path: Path) -> None:
    _make_real_source_files(tmp_path)
    output_path = tmp_path / "output.mp4"
    captured_command = {}

    def _fake_run(command, **kwargs):
        captured_command["command"] = command
        return _fake_completed_process(output_path)

    with patch("app.services.video_renderer.ffmpeg_available", return_value=True):
        with patch("subprocess.run", side_effect=_fake_run):
            render_static_video(
                audio_dir=tmp_path,
                artwork_dir=tmp_path,
                output_dir=tmp_path,
                audio_filename="audio.wav",
                artwork_filename="cover.png",
                output_filename="output.mp4",
                audio_start_seconds=12.5,
                audio_duration_seconds=28.0,
            )

    command = captured_command["command"]
    audio_path_str = str((tmp_path / "audio.wav").resolve())
    audio_input_index = command.index(audio_path_str)
    # The immediately-preceding tokens must be exactly
    # ["-ss", "12.5", "-t", "28.0", "-i"].
    assert command[audio_input_index - 5 : audio_input_index] == [
        "-ss", "12.5", "-t", "28.0", "-i",
    ]


def test_negative_audio_start_seconds_is_rejected(tmp_path: Path) -> None:
    with patch("app.services.video_renderer.ffmpeg_available", return_value=True):
        with pytest.raises(ValueError, match="audio_start_seconds"):
            render_static_video(
                audio_dir=tmp_path,
                artwork_dir=tmp_path,
                output_dir=tmp_path,
                audio_filename="audio.wav",
                artwork_filename="cover.png",
                output_filename="output.mp4",
                audio_start_seconds=-1.0,
            )


def test_non_positive_audio_duration_is_rejected(tmp_path: Path) -> None:
    with patch("app.services.video_renderer.ffmpeg_available", return_value=True):
        with pytest.raises(ValueError, match="audio_duration_seconds"):
            render_static_video(
                audio_dir=tmp_path,
                artwork_dir=tmp_path,
                output_dir=tmp_path,
                audio_filename="audio.wav",
                artwork_filename="cover.png",
                output_filename="output.mp4",
                audio_duration_seconds=0,
            )


@pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg/ffprobe not available on this machine")
def test_real_render_with_trim_produces_the_requested_clip_duration(tmp_path: Path) -> None:
    audio_path = tmp_path / "audio.wav"
    with wave.open(str(audio_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(8000)
        wav_file.writeframes(b"\x00\x00" * 8000 * 10)  # 10 real seconds

    Image.new("RGB", (100, 100)).save(tmp_path / "cover.png")

    output_path = render_static_video(
        audio_dir=tmp_path,
        artwork_dir=tmp_path,
        output_dir=tmp_path,
        audio_filename="audio.wav",
        artwork_filename="cover.png",
        output_filename="short.mp4",
        width=1080,
        height=1920,
        audio_start_seconds=3.0,
        audio_duration_seconds=4.0,
    )

    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-show_entries", "format=duration",
            "-of", "json",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    probe_data = json.loads(probe.stdout)

    assert probe_data["streams"][0]["width"] == 1080
    assert probe_data["streams"][0]["height"] == 1920
    # Tight tolerance, not the old 0.3s slop -- -shortest alone overran a
    # requested trim by several real seconds (see the explicit output -t
    # cap this now relies on); a loose tolerance here would have hidden
    # exactly the bug that a real ffprobe check against production audio
    # caught. AAC's own small encoder priming delay is the only real
    # source of slack left.
    assert float(probe_data["format"]["duration"]) == pytest.approx(4.0, abs=0.05)


@pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg/ffprobe not available on this machine")
def test_real_render_trim_is_precise_on_a_long_source_file(tmp_path: Path) -> None:
    # Regression test for a real bug found during manual verification:
    # -shortest alone, combined with the looped stillimage input, overran
    # a 28s-requested trim by 3.2s on a real ~895s production audio file
    # (31.2s delivered instead of 28.0s) -- small-file tests didn't
    # reliably surface this at a smaller scale, so this test deliberately
    # uses a long source file and an offset far into it, matching the
    # real shorts_pipeline.py usage pattern (a ~14:55 track, clips
    # starting hundreds of seconds in).
    audio_path = tmp_path / "long_audio.wav"
    with wave.open(str(audio_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(8000)
        wav_file.writeframes(b"\x00\x00" * 8000 * 120)  # 120 real seconds

    Image.new("RGB", (100, 100)).save(tmp_path / "cover.png")

    output_path = render_static_video(
        audio_dir=tmp_path,
        artwork_dir=tmp_path,
        output_dir=tmp_path,
        audio_filename="long_audio.wav",
        artwork_filename="cover.png",
        output_filename="clip.mp4",
        width=1080,
        height=1920,
        audio_start_seconds=87.0,
        audio_duration_seconds=28.0,
    )

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(output_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    duration = float(json.loads(probe.stdout)["format"]["duration"])

    assert duration == pytest.approx(28.0, abs=0.05)


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
