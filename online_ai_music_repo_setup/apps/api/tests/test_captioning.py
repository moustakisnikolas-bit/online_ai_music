import sys
import types
from pathlib import Path

from app.services.captioning import _format_timestamp, transcribe_to_srt


def test_format_timestamp_basic() -> None:
    assert _format_timestamp(0.0) == "00:00:00,000"
    assert _format_timestamp(1.5) == "00:00:01,500"
    assert _format_timestamp(61.25) == "00:01:01,250"
    assert _format_timestamp(3661.001) == "01:01:01,001"


def test_format_timestamp_rounds_milliseconds() -> None:
    assert _format_timestamp(1.9996) == "00:00:02,000"


class _FakeSegment:
    def __init__(self, start: float, end: float, text: str) -> None:
        self.start = start
        self.end = end
        self.text = text


class _FakeWhisperModel:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def transcribe(self, _audio_path: str):
        segments = [
            _FakeSegment(0.0, 1.5, " Hello there "),
            _FakeSegment(1.5, 3.0, "General Kenobi"),
        ]
        return segments, object()


def test_transcribe_to_srt_writes_well_formed_output(monkeypatch, tmp_path: Path) -> None:
    fake_module = types.ModuleType("faster_whisper")
    fake_module.WhisperModel = _FakeWhisperModel
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)

    audio_path = tmp_path / "narration.wav"
    audio_path.write_bytes(b"")
    output_dir = tmp_path / "captions"

    srt_path = transcribe_to_srt(audio_path, output_dir)

    assert srt_path == output_dir / "narration.srt"
    content = srt_path.read_text(encoding="utf-8")

    assert content == (
        "1\n"
        "00:00:00,000 --> 00:00:01,500\n"
        "Hello there\n"
        "\n"
        "2\n"
        "00:00:01,500 --> 00:00:03,000\n"
        "General Kenobi\n"
        "\n"
    )
