import json
import struct
import wave
from pathlib import Path

import pytest

from app.audio import sample_library
from app.audio.dsp import load_sample_layer


def _write_manifest(tmp_path: Path, entries: list[dict]) -> Path:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"samples": entries}), encoding="utf-8")
    return manifest_path


def _write_tone_wav(
    path: Path,
    *,
    frame_count: int = 4000,
    sample_rate: int = 8000,
) -> None:
    with wave.open(str(path), "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        frames = bytearray()

        for index in range(frame_count):
            value = int(10000 * ((index % 100) / 100 - 0.5))
            frames.extend(struct.pack("<h", value))

        wav_file.writeframes(bytes(frames))


def test_load_manifest_returns_empty_list_when_missing(tmp_path: Path) -> None:
    assert sample_library.load_manifest(tmp_path / "missing.json") == []


def test_get_sample_found_and_not_found(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path,
        [
            {
                "id": "rain-01",
                "label": "Rain",
                "category": "rain",
                "filename": "rain-01.wav",
                "license": "CC0",
            }
        ],
    )

    sample = sample_library.get_sample("rain-01", manifest_path)
    assert sample.label == "Rain"

    with pytest.raises(ValueError, match="Unknown natural sound sample"):
        sample_library.get_sample("does-not-exist", manifest_path)


def test_resolve_sample_audio_path_missing_file_raises(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path,
        [
            {
                "id": "rain-01",
                "label": "Rain",
                "category": "rain",
                "filename": "rain-01.wav",
                "license": "CC0",
            }
        ],
    )
    sample = sample_library.get_sample("rain-01", manifest_path)

    with pytest.raises(FileNotFoundError):
        sample_library.resolve_sample_audio_path(sample, tmp_path)


def test_resolve_sample_audio_path_rejects_path_traversal(tmp_path: Path) -> None:
    sample = sample_library.NaturalSoundSample(
        id="malicious",
        label="Malicious",
        category="rain",
        filename="../secrets.wav",
        license="CC0",
    )

    with pytest.raises(ValueError, match="Invalid sample filename"):
        sample_library.resolve_sample_audio_path(sample, tmp_path)


def test_resolve_sample_audio_path_returns_existing_file(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path,
        [
            {
                "id": "rain-01",
                "label": "Rain",
                "category": "rain",
                "filename": "rain-01.wav",
                "license": "CC0",
            }
        ],
    )
    sample = sample_library.get_sample("rain-01", manifest_path)
    audio_path = tmp_path / "rain-01.wav"
    _write_tone_wav(audio_path)

    resolved = sample_library.resolve_sample_audio_path(sample, tmp_path)
    assert resolved == audio_path.resolve()


def test_list_samples_round_trips_manifest_fields(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path,
        [
            {
                "id": "rain-01",
                "label": "Rain",
                "category": "rain",
                "filename": "rain-01.wav",
                "license": "CC0",
                "source_url": "https://example.com/rain-01",
                "attribution": None,
            }
        ],
    )

    manifest_path = tmp_path / "manifest.json"
    entries = sample_library.list_samples(manifest_path)
    assert entries == [
        {
            "id": "rain-01",
            "label": "Rain",
            "category": "rain",
            "filename": "rain-01.wav",
            "license": "CC0",
            "source_url": "https://example.com/rain-01",
            "attribution": None,
        }
    ]


def test_load_sample_layer_loops_to_target_duration(tmp_path: Path) -> None:
    audio_path = tmp_path / "tone.wav"
    _write_tone_wav(audio_path, frame_count=4000, sample_rate=8000)

    result = load_sample_layer(audio_path, duration_seconds=2, sample_rate=8000)

    assert len(result) == 16000
    assert result.dtype.kind == "f"
    assert float(result.max()) <= 1.0
    assert float(result.min()) >= -1.0


def test_load_sample_layer_resamples_when_rates_differ(tmp_path: Path) -> None:
    audio_path = tmp_path / "tone.wav"
    _write_tone_wav(audio_path, frame_count=4000, sample_rate=8000)

    result = load_sample_layer(audio_path, duration_seconds=1, sample_rate=16000)

    assert len(result) == 16000
