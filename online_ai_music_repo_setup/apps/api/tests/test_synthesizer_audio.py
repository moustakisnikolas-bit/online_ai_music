import wave
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from app.audio.soundfont_synth import soundfont_synth_available
from app.audio.types import AudioMode
from app.schemas.audio import AudioGenerationRequest
from app.services import audio_generator
from app.services.audio_generator import generate_audio


def _valid_synth_kwargs() -> dict:
    return {
        "title": "Synth Test",
        "mode": AudioMode.SYNTHESIZER,
        "synth_instrument": "warm_pad",
        "synth_root_note": "C4",
        "synth_scale": "major",
        "synth_pattern": "up",
        "duration_seconds": 2,
        "sample_rate": 8000,
        "amplitude": 0.2,
        "fade_in_seconds": 0,
        "fade_out_seconds": 0,
        "seed": 7,
    }


def test_synthesizer_request_requires_all_fields() -> None:
    kwargs = _valid_synth_kwargs()
    del kwargs["synth_instrument"]

    with pytest.raises(ValidationError, match="synth_instrument"):
        AudioGenerationRequest(**kwargs)


def test_synthesizer_rejects_unknown_instrument() -> None:
    kwargs = _valid_synth_kwargs()
    kwargs["synth_instrument"] = "kazoo"

    with pytest.raises(ValidationError, match="Unknown synth_instrument"):
        AudioGenerationRequest(**kwargs)


def test_synthesizer_rejects_unknown_scale() -> None:
    kwargs = _valid_synth_kwargs()
    kwargs["synth_scale"] = "phrygian_dominant"

    with pytest.raises(ValidationError, match="Unknown synth_scale"):
        AudioGenerationRequest(**kwargs)


def test_synthesizer_rejects_bad_root_note() -> None:
    kwargs = _valid_synth_kwargs()
    kwargs["synth_root_note"] = "H4"

    with pytest.raises(ValidationError, match="Invalid note name"):
        AudioGenerationRequest(**kwargs)


def test_synthesizer_rejects_long_form() -> None:
    kwargs = _valid_synth_kwargs()
    kwargs["long_form"] = True

    with pytest.raises(ValidationError, match="long_form"):
        AudioGenerationRequest(**kwargs)


def test_synthesizer_dispatch_reaches_render_pattern(monkeypatch, tmp_path: Path) -> None:
    calls = []

    def _fake_render_pattern(events, duration_seconds, sample_rate, program_number, cc_values):
        calls.append((len(events), duration_seconds, sample_rate, program_number, cc_values))
        return np.zeros(duration_seconds * sample_rate, dtype=np.float32)

    monkeypatch.setattr(audio_generator, "render_pattern", _fake_render_pattern)

    request = AudioGenerationRequest(**_valid_synth_kwargs())
    result = generate_audio(request, tmp_path)

    assert result.mode == "synthesizer"
    assert len(calls) == 1
    note_count, duration_seconds, sample_rate, program_number, cc_values = calls[0]
    assert note_count > 0
    assert duration_seconds == 2
    assert sample_rate == 8000
    assert program_number == 89  # warm_pad's GM program number
    assert set(cc_values.keys()) == {71, 72, 73, 74}


def test_synthesizer_composes_with_textures(monkeypatch, tmp_path: Path) -> None:
    def _fake_render_pattern(events, duration_seconds, sample_rate, program_number, cc_values):
        return np.full(duration_seconds * sample_rate, 0.1, dtype=np.float32)

    monkeypatch.setattr(audio_generator, "render_pattern", _fake_render_pattern)

    kwargs = _valid_synth_kwargs()
    kwargs["textures"] = [{"texture_type": "rain", "gain": 0.3}]
    request = AudioGenerationRequest(**kwargs)

    result = generate_audio(request, tmp_path)

    assert result.mode == "synthesizer"
    with wave.open(result.file_path, "rb") as wav_file:
        assert wav_file.getnframes() == 16000


def test_synthesizer_raises_clear_error_when_unavailable(monkeypatch, tmp_path: Path) -> None:
    from app.audio import soundfont_synth

    monkeypatch.setattr(soundfont_synth, "soundfont_synth_available", lambda: False)

    request = AudioGenerationRequest(**_valid_synth_kwargs())

    with pytest.raises(ValueError, match="Synthesizer mode is not available"):
        generate_audio(request, tmp_path)


@pytest.mark.skipif(
    not soundfont_synth_available(),
    reason="FluidSynth/soundfont not available on this machine",
)
def test_synthesizer_real_end_to_end_render(tmp_path: Path) -> None:
    request = AudioGenerationRequest(**_valid_synth_kwargs())
    result = generate_audio(request, tmp_path)

    assert result.mode == "synthesizer"
    with wave.open(result.file_path, "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getframerate() == 8000
        assert wav_file.getnframes() == 16000
