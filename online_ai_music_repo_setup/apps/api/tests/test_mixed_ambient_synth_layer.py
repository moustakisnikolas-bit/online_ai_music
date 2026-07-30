import wave
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from app.audio.soundfont_synth import soundfont_synth_available
from app.audio.types import AudioMode, ChannelMode
from app.schemas.audio import AudioGenerationRequest
from app.services import audio_generator
from app.services.audio_generator import generate_audio


def _synth_layer(**overrides) -> dict:
    layer = {
        "kind": "synth",
        "instrument": "warm_pad",
        "root_note": "C4",
        "scale": "major",
        "pattern": "up",
        "gain": 0.5,
    }
    layer.update(overrides)
    return layer


def test_synth_layer_rejects_unknown_instrument() -> None:
    with pytest.raises(ValidationError, match="Unknown synth instrument"):
        AudioGenerationRequest(
            title="Bad Instrument",
            mode=AudioMode.MIXED_AMBIENT,
            ambient_layers=[
                {"kind": "noise", "noise_type": "brown_noise", "gain": 0.4},
                _synth_layer(instrument="kazoo"),
            ],
            duration_seconds=2,
            sample_rate=8000,
        )


def test_synth_layer_rejects_unknown_scale() -> None:
    with pytest.raises(ValidationError, match="Unknown synth scale"):
        AudioGenerationRequest(
            title="Bad Scale",
            mode=AudioMode.MIXED_AMBIENT,
            ambient_layers=[_synth_layer(scale="phrygian_dominant")],
            duration_seconds=2,
            sample_rate=8000,
        )


def test_synth_layer_rejects_bad_root_note() -> None:
    with pytest.raises(ValidationError, match="Invalid note name"):
        AudioGenerationRequest(
            title="Bad Root Note",
            mode=AudioMode.MIXED_AMBIENT,
            ambient_layers=[_synth_layer(root_note="H4")],
            duration_seconds=2,
            sample_rate=8000,
        )


def test_synth_layer_dispatch_reaches_render_pattern(monkeypatch, tmp_path: Path) -> None:
    calls = []

    def _fake_render_pattern(events, duration_seconds, sample_rate, program_number, cc_values):
        calls.append((len(events), duration_seconds, sample_rate, program_number, cc_values))
        return np.zeros(duration_seconds * sample_rate, dtype=np.float32)

    monkeypatch.setattr(audio_generator, "render_pattern", _fake_render_pattern)

    request = AudioGenerationRequest(
        title="Mixed Ambient With Melody",
        mode=AudioMode.MIXED_AMBIENT,
        channels=ChannelMode.MONO,
        ambient_layers=[
            {"kind": "noise", "noise_type": "brown_noise", "gain": 0.4},
            _synth_layer(),
        ],
        duration_seconds=2,
        sample_rate=8000,
        fade_in_seconds=0,
        fade_out_seconds=0,
        seed=7,
    )
    result = generate_audio(request, tmp_path)

    assert result.mode == "mixed_ambient"
    assert len(calls) == 1
    note_count, duration_seconds, sample_rate, program_number, cc_values = calls[0]
    assert note_count > 0
    assert duration_seconds == 2
    assert sample_rate == 8000
    assert program_number == 89  # warm_pad's GM program number
    assert set(cc_values.keys()) == {71, 72, 73, 74}

    with wave.open(result.file_path, "rb") as wav_file:
        assert wav_file.getnframes() == 16000


def test_synth_layer_is_never_a_ducking_trigger(monkeypatch, tmp_path: Path) -> None:
    # A melody line shouldn't get treated as an event-type texture trigger
    # -- only kind="texture" layers with an event-driven texture_type can
    # trigger sidechain ducking (see _DUCKING_TEXTURE_TYPES). This just
    # confirms a synth layer alongside a real trigger texture doesn't
    # error out and produces the expected duration.
    def _fake_render_pattern(events, duration_seconds, sample_rate, program_number, cc_values):
        return np.full(duration_seconds * sample_rate, 0.05, dtype=np.float32)

    monkeypatch.setattr(audio_generator, "render_pattern", _fake_render_pattern)

    request = AudioGenerationRequest(
        title="Melody Plus Thunder",
        mode=AudioMode.MIXED_AMBIENT,
        channels=ChannelMode.MONO,
        ambient_layers=[
            {"kind": "noise", "noise_type": "brown_noise", "gain": 0.4},
            {"kind": "texture", "texture_type": "thunder", "gain": 0.5},
            _synth_layer(),
        ],
        duration_seconds=3,
        sample_rate=8000,
        fade_in_seconds=0,
        fade_out_seconds=0,
        seed=3,
    )
    result = generate_audio(request, tmp_path)

    with wave.open(result.file_path, "rb") as wav_file:
        assert wav_file.getnframes() == 24000


def test_synth_layer_raises_clear_error_when_unavailable(monkeypatch, tmp_path: Path) -> None:
    from app.audio import soundfont_synth

    monkeypatch.setattr(soundfont_synth, "soundfont_synth_available", lambda: False)

    request = AudioGenerationRequest(
        title="Unavailable Synth",
        mode=AudioMode.MIXED_AMBIENT,
        ambient_layers=[
            {"kind": "noise", "noise_type": "brown_noise", "gain": 0.4},
            _synth_layer(),
        ],
        duration_seconds=2,
        sample_rate=8000,
    )

    with pytest.raises(ValueError, match="Synthesizer mode is not available"):
        generate_audio(request, tmp_path)


@pytest.mark.skipif(
    not soundfont_synth_available(),
    reason="FluidSynth/soundfont not available on this machine",
)
def test_synth_layer_real_end_to_end_render(tmp_path: Path) -> None:
    request = AudioGenerationRequest(
        title="Real Melody Bed",
        mode=AudioMode.MIXED_AMBIENT,
        channels=ChannelMode.MONO,
        ambient_layers=[
            {"kind": "noise", "noise_type": "brown_noise", "gain": 0.4},
            _synth_layer(),
        ],
        duration_seconds=2,
        sample_rate=8000,
        fade_in_seconds=0,
        fade_out_seconds=0,
    )
    result = generate_audio(request, tmp_path)

    with wave.open(result.file_path, "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getframerate() == 8000
        assert wav_file.getnframes() == 16000
